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
