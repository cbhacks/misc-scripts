#
# CBHacks Script for LatestFiles table updates
# Copyright (c) 2019  "chekwob" <chek@wobbyworks.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

#
# This script is intended to run on AWS Lambda. The script should accompany a
# DynamoDB table with at least the following attributes:
#
#   Bucket:    (string, partition key)
#   Channel:   (string, sort key)
#   Pattern:   (string)
#   ObjectKey: (string)
#
# The script should have the following permissions for the table:
#
#   Query
#   UpdateItem
#
# The script should be triggered by S3 ObjectCreated events for each bucket
# whose name matches the Bucket attribute of an item in the table and whose
# object key could (regex) match a Pattern attribute of one or more of those
# items.
#
# When triggered, the script updates every ObjectKey attribute for each table
# item with the bucket name Bucket and whose (regex) Pattern attribute matches
# the object key, but only if the new object key is greater than the existing
# one in the database.
#
# The purpose of this script is to ensure that, except during the brief period
# between an S3 PUT and the script exection completion, each ObjectKey item
# attribute holds the "greatest" key in the Bucket which matches the pattern.
# This may be used, for example, to enable cheap lookups of the latest build
# of a particular software package (stored on S3) without using any costly and
# eventually-consistent List operations.
#
# This script only tracks object creation, and will not handle object deletion
# to in any way "roll back" the ObjectKey field.
#
# ObjectKey comparison is done bytewise using the UTF-8 encoding of the string.
# For ASCII text, this is a lexicographical ordering.
#
# The table name is hardcoded in the script, and may be adjusted as necessary.
#
# For bootstrapping purposes, this script may be invoked directly outside of
# Lambda with a bucket name and object key to immediately populate the tables
# with initial ObjectKey values. Presence of the given bucket and object on S3
# are not checked.
#

import re
import sys
import boto3
import botocore
import json

table_name = 'LatestFiles'

db = boto3.client('dynamodb')

def lambda_handler(event, context):
    assert len(event['Records']) == 1
    if 'Sns' in event['Records'][0]:
        # If this event was delivered via SNS, unwrap it to retrieve the true
        # S3 event object.
        event = json.loads(event['Records'][0]['Sns']['Message'])
        assert len(event['Records']) == 1
    s3ev = event['Records'][0]['s3']
    print('========================================')
    print(f'Bucket:  {s3ev["bucket"]["name"]}')
    print(f'Key:     {s3ev["object"]["key"]}')
    print('========================================')
    print()
    resume = {}
    while True:
        qr = db.query(
            TableName=table_name,
            ProjectionExpression='Channel,Pattern',
            KeyConditionExpression='#BKT = :bucket',
            ExpressionAttributeValues={
                ':bucket': { 'S': s3ev['bucket']['name'] }
            },
            ExpressionAttributeNames={
                '#BKT': 'Bucket'
            },
            **resume
        )
        for item in qr['Items']:
            assert 'Channel' in item
            assert 'Pattern' in item
            assert 'S' in item['Pattern']
            if not re.search(item['Pattern']['S'], s3ev['object']['key']):
                continue
            try:
                print(f'    Updating {item["Channel"]["S"]}...')
                db.update_item(
                    TableName=table_name,
                    Key={
                        'Bucket': { 'S': s3ev['bucket']['name'] },
                        'Channel': item['Channel']
                    },
                    UpdateExpression='SET ObjectKey = :key',
                    ConditionExpression='attribute_not_exists(ObjectKey) OR (ObjectKey < :key)',
                    ExpressionAttributeValues={
                        ':key': { 'S': s3ev['object']['key'] }
                    }
                )
                print('        OK')
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    raise
                print('        Already up to date.')
        if 'LastEvaluatedKey' in qr:
            resume = { 'ExclusiveStartKey': qr['LastEvaluatedKey'] }
        else:
            break

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 latestfiles_update.py <bucket-name> <object-key>")
        sys.exit()
    lambda_handler({
        'Records': [{
            's3': {
                'bucket': {
                    'name': sys.argv[1]
                },
                'object': {
                    'key': sys.argv[2]
                }
            }
        }]
    }, None)
