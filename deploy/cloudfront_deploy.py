import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "outputs" / "aws_state.json"
OUT = ROOT / "outputs"
LOG = ROOT / "logs" / "cloudfront_deployment.json"


def aws(*args):
    command = ["aws", "--profile", "csce412", "--region", "us-east-1",
               "--no-cli-pager", *args]
    p = subprocess.run(command, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout.strip()


def save(path, obj):
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def main():
    s = json.loads(STATE.read_text(encoding="utf-8-sig"))
    identity = json.loads(aws("sts", "get-caller-identity"))
    account = identity["Account"]
    bucket = s["bucket"]

    if bucket != "csce412-project5-" + account:
        raise ValueError("Bucket and AWS account do not match")

    print("Account:", account, "Bucket:", bucket)
    print("Will create CloudFront OAC, distribution, and S3 access policy.")

    if input("Type CLOUDFRONT to approve: ").strip() != "CLOUDFRONT":
        print("Cancelled")
        return

    try:
        if not s.get("oac_id"):
            response = json.loads(aws(
                "cloudfront", "create-origin-access-control",
                "--origin-access-control-config",
                "Name=csce412-" + account +
                "-oac,SigningProtocol=sigv4,"
                "SigningBehavior=always,OriginAccessControlOriginType=s3"
            ))
            s["oac_id"] = response["OriginAccessControl"]["Id"]
            save(STATE, s)

        print("OAC:", s["oac_id"])

        if not s.get("cloudfront"):
            origin_id = "private-s3"
            methods = {"Quantity": 2, "Items": ["GET", "HEAD"]}

            config = {
                "CallerReference": "csce412-project5-" + account,
                "Comment": "CSCE412 private portfolio website",
                "Enabled": True,
                "DefaultRootObject": "index.html",
                "PriceClass": "PriceClass_100",
                "Origins": {
                    "Quantity": 1,
                    "Items": [{
                        "Id": origin_id,
                        "DomainName": bucket + ".s3.us-east-1.amazonaws.com",
                        "S3OriginConfig": {"OriginAccessIdentity": ""},
                        "OriginAccessControlId": s["oac_id"]
                    }]
                },
                "DefaultCacheBehavior": {
                    "TargetOriginId": origin_id,
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": {
                        **methods,
                        "CachedMethods": methods
                    },
                    "ForwardedValues": {
                        "QueryString": False,
                        "Cookies": {"Forward": "none"}
                    },
                    "Compress": True,
                    "MinTTL": 0,
                    "DefaultTTL": 300,
                    "MaxTTL": 86400
                },
                "CustomErrorResponses": {
                    "Quantity": 2,
                    "Items": [
                        {
                            "ErrorCode": code,
                            "ResponsePagePath": "/404.html",
                            "ResponseCode": "404",
                            "ErrorCachingMinTTL": 10
                        }
                        for code in (403, 404)
                    ]
                },
                "ViewerCertificate": {
                    "CloudFrontDefaultCertificate": True
                }
            }

            config_file = OUT / "cloudfront_config.json"
            save(config_file, config)

            response = json.loads(aws(
                "cloudfront", "create-distribution",
                "--distribution-config", "file://" + str(config_file)
            ))

            distribution = response["Distribution"]

            s["cloudfront"] = {
                "id": distribution["Id"],
                "domain": distribution["DomainName"]
            }
            s["phase"] = "CLOUDFRONT_CREATED"
            save(STATE, s)

        print("Distribution:", s["cloudfront"]["id"])

        try:
            response = json.loads(aws(
                "s3api", "get-bucket-policy", "--bucket", bucket
            ))
            policy = json.loads(response["Policy"])
        except RuntimeError as e:
            if "NoSuchBucketPolicy" not in str(e):
                raise
            policy = {"Version": "2012-10-17", "Statement": []}

        statement = {
            "Sid": "AllowCloudFrontOACRead",
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::" + bucket + "/*",
            "Condition": {
                "StringEquals": {
                    "AWS:SourceArn":
                        "arn:aws:cloudfront::" + account +
                        ":distribution/" + s["cloudfront"]["id"]
                }
            }
        }

        policy["Statement"] = [
            item for item in policy["Statement"]
            if item.get("Sid") != statement["Sid"]
        ] + [statement]

        policy_file = OUT / "cloudfront_bucket_policy.json"
        save(policy_file, policy)

        aws(
            "s3api", "put-bucket-policy",
            "--bucket", bucket,
            "--policy", "file://" + str(policy_file)
        )

        save(LOG, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_tool": "cloudfront_deployment",
            "result": "SUCCESS",
            "distribution": s["cloudfront"],
            "bucket": bucket
        })

        print("CloudFront URL: https://" + s["cloudfront"]["domain"] + "/")
        print("S3 access granted only to the CloudFront distribution.")

    except Exception as e:
        save(LOG, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_tool": "cloudfront_deployment",
            "result": "FAILED",
            "error": str(e),
            "state": s
        })
        raise


if __name__ == "__main__":
    main()
