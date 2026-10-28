# ==============================================================================
# Outputs
# ==============================================================================

# ------------------------------------------------------------------------------
# Auth Outputs (Lab 4: auth.yml / peach-auth)
# ------------------------------------------------------------------------------

output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.this.arn
}

output "user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  value       = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  description = "Fully qualified Cognito domain name"
  value       = "${aws_cognito_user_pool_domain.this.domain}.auth.${var.region}.amazoncognito.com"
}

output "cognito_domain_prefix" {
  description = "Cognito Hosted UI / Managed Login Domain Prefix"
  value       = aws_cognito_user_pool_domain.this.domain
}

# ------------------------------------------------------------------------------
# Reports Outputs (Lab 5: reports.yml / peach-reports)
# ------------------------------------------------------------------------------

output "reports_bucket_name" {
  description = "Reports private S3 bucket name"
  value       = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  description = "Reports private S3 bucket ARN"
  value       = aws_s3_bucket.reports.arn
}

output "report_requests_queue_url" {
  description = "URL of the SQS queue for report requests"
  value       = aws_sqs_queue.report_requests.id
}

output "report_requests_queue_arn" {
  description = "ARN of the SQS queue for report requests"
  value       = aws_sqs_queue.report_requests.arn
}

output "report_requests_dlq_url" {
  description = "URL of the dead-letter queue for report requests"
  value       = aws_sqs_queue.report_requests_dlq.id
}

output "report_requests_dlq_arn" {
  description = "ARN of the dead-letter queue for report requests"
  value       = aws_sqs_queue.report_requests_dlq.arn
}

output "report_builder_function_name" {
  description = "Name of the report-builder Lambda function"
  value       = aws_lambda_function.report_builder.function_name
}

output "report_builder_function_arn" {
  description = "ARN of the report-builder Lambda function"
  value       = aws_lambda_function.report_builder.arn
}

output "report_mailer_function_name" {
  description = "Name of the report-mailer Lambda function"
  value       = aws_lambda_function.report_mailer.function_name
}

output "report_mailer_function_arn" {
  description = "ARN of the report-mailer Lambda function"
  value       = aws_lambda_function.report_mailer.arn
}

output "weekly_report_schedule_arn" {
  description = "ARN of the EventBridge Scheduler schedule"
  value       = aws_scheduler_schedule.weekly_report.arn
}

output "s3_endpoint_id" {
  description = "ID of the S3 Gateway VPC Endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "ses_domain_identity" {
  description = "SES domain identity"
  value       = aws_sesv2_email_identity.this.email_identity
}

# ------------------------------------------------------------------------------
# AI / Agenda Parser Outputs (Lab 6: template.yaml / parser.yaml / peach-parser)
# ------------------------------------------------------------------------------

output "parser_function_name" {
  description = "AI Agenda Parser Lambda function name"
  value       = aws_lambda_function.parser.function_name
}

output "parser_function_arn" {
  description = "AI Agenda Parser Lambda function ARN"
  value       = aws_lambda_function.parser.arn
}

output "parser_function_url" {
  description = "AI Agenda Parser Lambda public Function URL"
  value       = aws_lambda_function_url.parser.function_url
}
