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
sqs_url = 'https://sqs.ap-northeast-2.amazonaws.com/661798210997/my_queue_dl_test'
while True:
    for message_batch in gen_msg():
        sqs_client.send_message_batch(
            QueueUrl=sqs_url,
            Entries=[{"Id": str(uuid.uuid4()), "MessageBody": message["Body"]} for message in message_batch]
        )
    else:
        break
