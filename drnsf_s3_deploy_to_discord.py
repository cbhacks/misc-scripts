#
# CBHacks Script for DRNSF deployment to Discord
# Copyright (c) 2018-2019  "chekwob" <chek@wobbyworks.com>
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
# This script is intended to run on AWS Lambda. No privileges are required
# beyond the basic Lambda privileges. S3 ObjectCreated events should trigger
# the script, which then reports the object's existence to discord under a URL
# in the following form:
#
# https://{bucket-name}/{object-key}
#
# For example:
#
#   Bucket name:   example.com
#   Object key:    foo/bar.zip
#   Resulting URL: https://example.com/foo/bar.zip
#
# Naturally, you should be serving the S3 objects from a web server on the
# domain matching the bucket's name, otherwise the reported links will not be
# functional.
#
# This script is for the python 3.6 runtime on Lambda. Your upload package
# should include the 'requests' library and its dependencies.
#
# You must provide the following environment variables for configuration:
#
#   DISCORD_WEBHOOK: The webhook URL which the script should post to. This
#   should be a discordapp webhook, or one compatible with that API.
#
#   ADMIN_EMAIL: This should be a contact email address for someone responsible
#   for the administration of the script's execution. It is used for the 'From'
#   HTTP header in the Discord webhook request.
#
# You can test this script under Lambda using the following test event. Modify
# the object key and bucket name as you desire.
#
# {
#   "Records": [
#     {
#       "s3": {
#         "object": {
#           "key": "test-only-please-ignore"
#         },
#         "bucket": {
#           "name": "example.com"
#         }
#       }
#     }
#   ]
# }
#
# If your URL or discord message needs to be formatted differently, you should
# modify the script for this purpose.
#

import os
import requests
import json

assert 'DISCORD_WEBHOOK' in os.environ
assert 'ADMIN_EMAIL' in os.environ

req_headers = {
    'From': os.environ['ADMIN_EMAIL']
}

def lambda_handler(event, context):
    assert len(event['Records']) == 1
    if 'Sns' in event['Records'][0]:
        # If this event was delivered via SNS, unwrap it to retrieve the true
        # S3 event object.
        event = json.loads(event['Records'][0]['Sns']['Message'])
        assert len(event['Records']) == 1
    s3ev = event['Records'][0]['s3']
    requests.post(
        os.environ['DISCORD_WEBHOOK'],
        params={
            'wait': 'true'
        },
        json={
            'embeds': [
                {
                    'title': s3ev['object']['key'].split('/')[-1],
                    'url': 'https://{}/{}'.format(
                        s3ev['bucket']['name'],
                        s3ev['object']['key']
                    )
                }
            ]
        },
        headers=req_headers
    ).raise_for_status()
