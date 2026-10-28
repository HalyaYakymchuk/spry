# ==============================================================================
# Common Variables
# ==============================================================================

variable "project_name" {
  description = "Project name prefix used for naming and tagging reports and AI resources"
  type        = string
  default     = "peach"
}

variable "auth_project_name" {
  description = "Project name prefix used for naming Cognito auth resources (spry in Lab 4)"
  type        = string
  default     = "spry"
}

variable "region" {
  description = "AWS region for provisioning infrastructure"
  type        = string
  default     = "eu-north-1"
}

variable "stage" {
  description = "Deployment environment or stage (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

# ==============================================================================
# Auth Variables (Lab 4: auth.yml / peach-auth)
# ==============================================================================

variable "cognito_domain_prefix" {
  description = "Unique domain prefix for Cognito Hosted UI / Managed Login"
  type        = string
  default     = "peach-ayth-halya"
}

variable "cloudfront_domain" {
  description = "CloudFront distribution domain name for OAuth callback and logout URLs"
  type        = string
  default     = "d2l89vyn3q02js.cloudfront.net"
}

variable "frontend_port" {
  description = "Local frontend port for development OAuth callback URLs"
  type        = number
  default     = 3000
}

variable "google_client_id" {
  description = "Google OAuth 2.0 Client ID for Cognito Identity Provider"
  type        = string
  default     = ""
}

variable "google_client_secret" {
  description = "Google OAuth 2.0 Client Secret for Cognito Identity Provider"
  type        = string
  sensitive   = true
  default     = ""
}

# ==============================================================================
# Reports Variables (Lab 5: reports.yml / peach-reports)
# ==============================================================================

variable "vpc_id" {
  description = "VPC ID where the backend database and VPC Lambda run"
  type        = string
  default     = "vpc-03f80b68db03e5374"
}

variable "route_table_ids" {
  description = "Route table IDs to associate with the S3 Gateway VPC Endpoint"
  type        = list(string)
  default     = ["rtb-0322da6dc44314864"]
}

variable "subnet_ids" {
  description = "Subnet IDs for report builder Lambda VPC access"
  type        = list(string)
  default     = ["subnet-04fe7e79faf29e229", "subnet-09ed785e26f5e1f0b", "subnet-06d8b88438cdd7fe6"]
}

variable "security_group_ids" {
  description = "Security group IDs for report builder Lambda VPC access"
  type        = list(string)
  default     = ["sg-08273d9ca20985b05"]
}

variable "reports_image_uri" {
  description = "Fully qualified container image URI in ECR for reports builder Lambda"
  type        = string
  default     = "640012953957.dkr.ecr.eu-north-1.amazonaws.com/peach-backend:reports-step4"
}

variable "database_url" {
  description = "Aurora database connection string or Secrets Manager reference"
  type        = string
  sensitive   = true
  default     = ""
}

variable "lambda_architecture" {
  description = "Lambda execution architecture (arm64 or x86_64)"
  type        = string
  default     = "arm64"
}

variable "reports_memory_size" {
  description = "Memory allocation for report builder Lambda (MB)"
  type        = number
  default     = 512
}

variable "reports_timeout" {
  description = "Timeout for report builder Lambda execution (seconds)"
  type        = number
  default     = 120
}

variable "domain_name" {
  description = "Domain name for SES identity and DKIM signing"
  type        = string
  default     = "spry.org.ua"
}

variable "hosted_zone_id" {
  description = "Optional Route 53 hosted zone ID for automatic DKIM DNS records"
  type        = string
  default     = ""
}

variable "sender_email" {
  description = "Verified SES email address used as the sender"
  type        = string
  default     = "galyayakymchuk19@gmail.com"
}

variable "recipient_email" {
  description = "Recipient email address for weekly reports"
  type        = string
  default     = "galyayakymchuk19@gmail.com"
}

# ==============================================================================
# AI / Agenda Parser Variables (Lab 6: template.yaml / parser.yaml / peach-parser)
# ==============================================================================

variable "ai_image_uri" {
  description = "Fully qualified container image URI in ECR for AI agenda parser Lambda"
  type        = string
  default     = "640012953957.dkr.ecr.eu-north-1.amazonaws.com/peach-backend:parser-step3"
}

variable "ai_memory_size" {
  description = "Memory allocation for AI agenda parser Lambda (MB)"
  type        = number
  default     = 512
}

variable "ai_timeout" {
  description = "Timeout for AI agenda parser Lambda execution (seconds)"
  type        = number
  default     = 30
}

variable "parser_model" {
  description = "Amazon Bedrock inference profile ID for Claude Haiku in eu-north-1"
  type        = string
  default     = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "cors_origins" {
  description = "List of allowed CORS origins for the parser Lambda function URL"
  type        = list(string)
  default = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://d2l89vyn3q02js.cloudfront.net"
  ]
}

variable "log_retention_days" {
  description = "Retention period for CloudWatch log groups in days"
  type        = number
  default     = 14
}

# ==============================================================================
# Upstream CloudFormation Stack Reference Variables
# ==============================================================================

variable "api_stack_name" {
  description = "Name of the upstream API / backend CloudFormation stack"
  type        = string
  default     = "peach-backend"
}

variable "frontend_stack_name" {
  description = "Name of the upstream frontend CloudFormation stack"
  type        = string
  default     = "peach-frontend"
}
