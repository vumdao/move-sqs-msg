#!/usr/bin/env python
"""
Move all the messages from one SQS queue to another.

Usage: redrive_sqs_queue.py --src-url=<SRC_QUEUE_URL> --dst-url=<DST_QUEUE_URL> --max-msg=<MAX_MSG_PROCESS>
       redrive_sqs_queue.py -h | --help
"""
import argparse
import itertools
import sys
import uuid
import boto3

from pprint import pprint


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Move all the messages from one SQS queue to another."
    )

    parser.add_argument("-s", "--src-url", required=True, help="Queue to read messages from")
    parser.add_argument("-d", "--dst-url", required=True, help="Queue to move messages to")
    parser.add_argument("-m", "--max-msg", required=False, type=int,
                        help="Max number of messages to process, no limit if not specify."
                             "Use this to limit the message processed to avoid pending message from others")
    parser.add_argument("-r", "--region", required=True, help="Region of the SQS queue, assume src and dest SQS"
                                                              "is in the same region")
    return parser.parse_args()


def get_messages_from_queue(sqs_client, queue_url, max_nr_msg=0):
    """Generates messages from an SQS queue.

    Note: this continues to generate messages until the queue is empty.
    Every message on the queue will be deleted.

    :param queue_url: URL of the SQS queue to read.
    :param sqs_client: boto3 sqs client to connect to AWS SQS
    """
    msg_processed = 0

    while True:
        resp = sqs_client.receive_message(
            QueueUrl=queue_url, AttributeNames=["All"], MaxNumberOfMessages=10, WaitTimeSeconds=1
        )

        entries = []
        try:
            msg_to_copy = resp["Messages"]
            if max_nr_msg > 0:
                if msg_processed >= max_nr_msg or msg_to_copy == 0:
                    pprint("Done")
                    break
                elif (len(msg_to_copy) + msg_processed) > max_nr_msg:
                    msg_to_copy = resp["Messages"][0: (max_nr_msg - msg_processed)]
            msg_processed += len(msg_to_copy)
        except KeyError:
            """ Don't return, need to delete messages """
            print(f'found no messages, Done!')
            return

        for msg in msg_to_copy:
            try:
                entries.append({"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]})
                yield msg
                if entries:
                    resp = sqs_client.delete_message_batch(QueueUrl=queue_url, Entries=entries)
                    if len(resp["Successful"]) != len(entries):
                        raise RuntimeError(f"Failed to delete messages: entries={entries!r} resp={resp!r}")
            except KeyError:
                print('failed parsing key')
                continue


def chunked_iterable(iterable, *, size):
    """
    Read ``iterable`` in chunks of size ``size``.
    """
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


if __name__ == "__main__":
    args = parse_args()

    src_queue_url = args.src_url
    dst_queue_url = args.dst_url
    region = args.region
    max_msg = args.max_msg
    if not max_msg:
        max_msg = 0

    if src_queue_url == dst_queue_url:
        sys.exit("Source and destination queues cannot be the same.")

    sqs_client = boto3.client("sqs", region_name=region)

    messages = get_messages_from_queue(sqs_client, queue_url=src_queue_url, max_nr_msg=max_msg)

    # The SendMessageBatch API supports sending up to ten messages at once.
    for message_batch in chunked_iterable(messages, size=10):
        print(f"Writing {len(message_batch):2d} messages to {dst_queue_url}")
        sqs_client.send_message_batch(
            QueueUrl=dst_queue_url,
            Entries=[{"Id": str(uuid.uuid4()), "MessageBody": message["Body"]} for message in message_batch]
        )
