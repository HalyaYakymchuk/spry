# ==============================================================================
# Reports Infrastructure (Lab 5: Migrated from reports.yml / peach-reports)
# ==============================================================================

# Logical ID: SesDomainIdentity
resource "aws_sesv2_email_identity" "this" {
  email_identity = var.domain_name

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

# Logical IDs: DkimRecord1, DkimRecord2, DkimRecord3 (Conditional on HasHostedZone)
resource "aws_route53_record" "ses_dkim" {
  count   = var.hosted_zone_id != "" ? 3 : 0
  zone_id = var.hosted_zone_id
  name    = "${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}._domainkey.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_sesv2_email_identity.this.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

# Logical ID: ReportMailerRole
resource "aws_iam_role" "report_mailer" {
  name = "peach-reports-ReportMailerRole-S5g4PWNwoL4S"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  ]

  inline_policy {
    name = "MailerS3Policy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = "s3:GetObject"
          Resource = [
            "arn:aws:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}/reports/*",
            "arn:aws:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}-${var.region}/reports/*"
          ]
        }
      ]
    })
  }

  inline_policy {
    name = "MailerSESPolicy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = ["ses:SendEmail", "ses:SendRawEmail"]
          Resource = "*"
        }
      ]
    })
  }

  lifecycle {
    ignore_changes = [name]
  }
}

# Logical ID: ReportMailerFunction
resource "aws_lambda_function" "report_mailer" {
  function_name = "${var.project_name}-report-mailer"
  description   = "${var.project_name} weekly report mailer"
  runtime       = "python3.11"
  handler       = "index.handler"
  role          = aws_iam_role.report_mailer.arn
  timeout       = 30
  memory_size   = 256
  filename      = "${path.module}/report_mailer.zip"

  environment {
    variables = {
      SENDER_EMAIL    = var.sender_email
      RECIPIENT_EMAIL = var.recipient_email
    }
  }
}

# Logical ID: ReportsBucket
resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-reports-${data.aws_caller_identity.current.account_id}-${var.region}"
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "ExpireReportsAfter90Days"
    status = "Enabled"

    filter {
      prefix = "reports/"
    }

    expiration {
      days = 90
    }
  }
}

# Logical ID: ReportMailerPermission (SourceArn without region)
resource "aws_lambda_permission" "report_mailer" {
  statement_id   = "ReportMailerPermission"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.report_mailer.arn
  principal      = "s3.amazonaws.com"
  source_arn     = "arn:aws:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}"
  source_account = data.aws_caller_identity.current.account_id
}

# Logical ID: ReportMailerRegionalPermission (SourceArn with region)
resource "aws_lambda_permission" "report_mailer_regional" {
  statement_id   = "ReportMailerRegionalPermission"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.report_mailer.arn
  principal      = "s3.amazonaws.com"
  source_arn     = "arn:aws:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}-${var.region}"
  source_account = data.aws_caller_identity.current.account_id
}

# Decoupled S3 Notification: Breaks circular dependency between Bucket and Lambda
resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.report_mailer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }

  depends_on = [
    aws_lambda_permission.report_mailer,
    aws_lambda_permission.report_mailer_regional
  ]
}

# Logical ID: ReportsS3Endpoint
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
}

# Logical ID: ReportRequestsDLQ
resource "aws_sqs_queue" "report_requests_dlq" {
  name                      = "${var.project_name}-report-requests-dlq"
  message_retention_seconds = 1209600
  max_message_size          = 1048576
}

# Logical ID: ReportRequestsQueue
resource "aws_sqs_queue" "report_requests" {
  name                       = "${var.project_name}-report-requests"
  visibility_timeout_seconds = 360
  max_message_size           = 1048576

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.report_requests_dlq.arn
    maxReceiveCount     = 3
  })
}

# Logical ID: ReportBuilderRole
resource "aws_iam_role" "report_builder" {
  name = "peach-reports-ReportBuilderRole-aaajijh91Zq1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  ]

  inline_policy {
    name = "PutReportsPolicy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = "s3:PutObject"
          Resource = "arn:aws:s3:::${aws_s3_bucket.reports.id}/reports/*"
        }
      ]
    })
  }

  inline_policy {
    name = "ConsumeReportRequestsPolicy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes"
          ]
          Resource = aws_sqs_queue.report_requests.arn
        }
      ]
    })
  }

  lifecycle {
    ignore_changes = [name]
  }
}

# Logical ID: ReportBuilderFunction
resource "aws_lambda_function" "report_builder" {
  function_name = "${var.project_name}-report-builder"
  description   = "${var.project_name} weekly report builder"
  package_type  = "Image"
  image_uri     = var.reports_image_uri
  architectures = [var.lambda_architecture]
  memory_size   = var.reports_memory_size
  timeout       = var.reports_timeout
  role          = aws_iam_role.report_builder.arn

  image_config {
    command = ["app.reports.lambda_handler.handler"]
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  environment {
    variables = {
      DATABASE_URL        = var.database_url != "" ? var.database_url : "{{resolve:secretsmanager:peach/backend/database-url:SecretString}}"
      REPORTS_BUCKET_NAME = aws_s3_bucket.reports.id
    }
  }
}

# Logical ID: ReportBuilderEventSourceMapping
resource "aws_lambda_event_source_mapping" "report_builder" {
  event_source_arn = aws_sqs_queue.report_requests.arn
  function_name    = aws_lambda_function.report_builder.arn
  batch_size       = 1
  enabled          = true
}

# Logical ID: SchedulerRole
resource "aws_iam_role" "scheduler" {
  name = "peach-reports-SchedulerRole-RRAgfX3tAYyv"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "scheduler.amazonaws.com"
        }
      }
    ]
  })

  inline_policy {
    name = "SendReportRequestsPolicy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect   = "Allow"
          Action   = "sqs:SendMessage"
          Resource = aws_sqs_queue.report_requests.arn
        }
      ]
    })
  }

  lifecycle {
    ignore_changes = [name]
  }
}

# Logical ID: WeeklyReportSchedule
resource "aws_scheduler_schedule" "weekly_report" {
  name                         = "${var.project_name}-weekly-report-schedule"
  description                  = "${var.project_name} weekly report generation schedule every Monday at 07:00 Europe/Kyiv"
  schedule_expression          = "cron(0 7 ? * MON *)"
  schedule_expression_timezone = "Europe/Kyiv"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sqs_queue.report_requests.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = "{\"week\": null, \"source\": \"schedule\"}"
  }
}
