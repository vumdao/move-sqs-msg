<p align="center">
  <a href="https://dev.to/vumdao">
    <img alt="Moving messages between SQS queues" src="https://dev-to-uploads.s3.amazonaws.com/i/hnekz2xrqbygji21ef0b.png" width="500" />
  </a>
</p>
<h1 align="center">
  <div><b>Moving messages between SQS queues</b></div>
</h1>

### - Dead-letter queue is used to send undeliverable messages to a dead-letter queue. Sometimes, for example, if there’s a bug in the worker code, you can configure SQS to send such problematic messages to a dead-letter queue (DLQ), where you can inspect them in isolation and work out what went wrong.

### - Once we’ve found the problem in the worker, fixed the bug and deployed a new version, we want to send all the messages from the DLQ back to the original input queue, so they can be processed by the updated worker. There’s no way to do this in SQS directly, so we’ve written a script to do it for us.

### - The automation script moves SQS messages between queues with proper way to avoid impact to other services which using the same queue. This post also provides CDK code to create SQS queues to test and the python script to generate a bunch of messages.

![Alt Text](https://dev-to-uploads.s3.amazonaws.com/i/tgo1wanmoti074utwzpj.png)

---

## What’s In This Document 
- [Create SQS queues using CDK](#-Create-SQS-queues-using-CDK)
- [Generate 100 Messages to Dead-letter Queue For Testing](#-Generate-100-Messages-to-Dead-letter-Queue-For-Testing)
- [Move All Messages At Once](#-Move-All-Messages-At-Once)
- [Move Half Messages To Avoid Workload](#-Move-Half-Messages-To-Avoid-Workload)
---
### 🚀 **[Create SQS queues using CDK](#-Create-SQS-queues-using-CDK)**
**1. Init  CDK project**
```
⚡ $ cdk init -l python
Applying project template app for python

# Welcome to your CDK Python project!

This is a blank project for Python development with CDK.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

✅ All done!
```

**2. Create CDK stacks**

- https://github.com/vumdao/move-sqs-msg/sqs_stack/sqs_stack_stack.py
```
from aws_cdk import (
    core,
    aws_sqs as sqs
)


class SqsStackStack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, env, **kwargs) -> None:
        super().__init__(scope, construct_id, env=env, **kwargs)

        # Create my-queue
        my_dl_queue = sqs.Queue(self, id="SQSTestDLQueueMovingMsg", queue_name="my_queue_dl_test")
        my_queue = sqs.Queue(self, id="SQSTestMovingMsg", queue_name="my_queue_test",
                             dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=1, queue=my_dl_queue)
                             )
```

- Deploy stacks
```
⚡ $ cdk ls
sqs-stack

⚡ $ cdk deploy 
sqs-stack: deploying...

 ✅  sqs-stack

Stack ARN:
arn:aws:cloudformation:ap-northeast-2:111111111111:stack/sqs-stack/ff3d8c20-6ee2-11eb-9f14-02d3758fdfbc
```

![Alt Text](https://dev-to-uploads.s3.amazonaws.com/i/hxduna2995kfkjemad9a.png)
![Alt Text](https://dev-to-uploads.s3.amazonaws.com/i/n0cwccuofiui7x86hdw7.png)

### 🚀 **[Generate 100 Messages to Dead-letter Queue For Testing](#-Generate-100-Messages-to-Dead-letter-Queue-For-Testing)**
- https://github.com/vumdao/move-sqs-msg/sendSQSMsg.py
```
import boto3
import uuid


def gen_msg():
    msg = list()
    for i in range(0, 100):
        body = f"Hello {i}"
        msg.append({"Body": body})
        if len(msg) > 9:
            yield msg
            msg = list()


sqs_client = boto3.client("sqs", region_name='ap-northeast-2')
sqs_url = 'https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_dl_test'
while True:
    for message_batch in gen_msg():
        sqs_client.send_message_batch(
            QueueUrl=sqs_url,
            Entries=[{"Id": str(uuid.uuid4()), "MessageBody": message["Body"]} for message in message_batch]
        )
    else:
        break
```
- Run
```
⚡ $ python sendSQSMsg.py
```
![Alt Text](https://dev-to-uploads.s3.amazonaws.com/i/ch9oau23zg40nzw9m1vk.png)

### 🚀 **[Move All Messages At Once](#-Move-All-Messages-At-Once)**
- https://github.com/vumdao/move-sqs-msg/redrive_sqs_queue.py
```
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
            QueueUrl=queue_url, AttributeNames=["All"], MaxNumberOfMessages=10
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
        except KeyError as err:
            """ Don't return, need to delete messages """
            print(f'found no messages')
            msg_to_copy = list()

        for msg in msg_to_copy:
            try:
                entries.append({"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]})
                yield msg
            except KeyError:
                print('failed parsing key')
                continue
        if entries:
            resp = sqs_client.delete_message_batch(QueueUrl=queue_url, Entries=entries)
            if len(resp["Successful"]) != len(entries):
                raise RuntimeError(f"Failed to delete messages: entries={entries!r} resp={resp!r}")


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
```

- Run
```
⚡ $ python redrive_sqs_queue.py -s https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_dl_test -d https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test -r ap-northeast-2 
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
found no messages, Done!
```

### 🚀 **[Move Half Messages To Avoid Workload](#-Move-Half-Messages-To-Avoid-Workload)**
```
⚡ $ python redrive_sqs_queue.py -s https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_dl_test -d https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test -r ap-northeast-2 -m 50
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
Writing 10 messages to https://sqs.ap-northeast-2.amazonaws.com/111111111111/my_queue_test
'Done'
```
![Alt Text](https://dev-to-uploads.s3.amazonaws.com/i/aiju9ljei38ll8xz4lng.png)

<h3 align="center">
  <a href="https://dev.to/vumdao">:stars: Blog</a>
  <span> · </span>
  <a href="https://github.com/vumdao/">Github</a>
  <span> · </span>
  <a href="https://vumdao.hashnode.dev/">Web</a>
  <span> · </span>
  <a href="https://www.linkedin.com/in/vu-dao-9280ab43/">Linkedin</a>
  <span> · </span>
  <a href="https://www.linkedin.com/groups/12488649/">Group</a>
  <span> · </span>
  <a href="https://www.facebook.com/CloudOpz-104917804863956">Page</a>
  <span> · </span>
  <a href="https://twitter.com/VuDao81124667">Twitter :stars:</a>
</h3>