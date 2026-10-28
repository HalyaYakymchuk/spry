# ==============================================================================
# Upstream CloudFormation Stacks & AWS Data Sources
# ==============================================================================

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_cloudformation_stack" "api" {
  name = var.api_stack_name
}

data "aws_cloudformation_stack" "frontend" {
  name = var.frontend_stack_name
}
