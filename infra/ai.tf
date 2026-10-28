# ==============================================================================
# AI Agenda Parser Infrastructure (Lab 6: Migrated from parser.yaml / template.yaml)
# ==============================================================================

# Logical ID: ParserExecutionRole
resource "aws_iam_role" "parser" {
  name = "${var.project_name}-agenda-parser-role"

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
    name = "BedrockInvokePolicy"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Effect = "Allow"
          Action = [
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream",
            "bedrock-mantle:CreateInference"
          ]
          Resource = "*"
        }
      ]
    })
  }
}

# Logical ID: ParserLogGroup
resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = var.log_retention_days
}

# Logical ID: ParserFunction
resource "aws_lambda_function" "parser" {
  function_name = "${var.project_name}-agenda-parser"
  description   = "${var.project_name} AI agenda parser (Bedrock Claude eu-north-1)"
  package_type  = "Image"
  image_uri     = var.ai_image_uri
  architectures = [var.lambda_architecture]
  memory_size   = var.ai_memory_size
  timeout       = var.ai_timeout
  role          = aws_iam_role.parser.arn

  image_config {
    command = ["app.ai.agenda_lambda.handler"]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser.name
  }

  environment {
    variables = {
      PARSER_MODEL         = var.parser_model
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.this.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.web.id
      COGNITO_REGION       = var.region
    }
  }

  depends_on = [aws_cloudwatch_log_group.parser]
}

# Logical ID: ParserFunctionUrl
resource "aws_lambda_function_url" "parser" {
  function_name      = aws_lambda_function.parser.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = var.cors_origins
    allow_methods = ["POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 86400
  }
}

# Logical ID: ParserFunctionUrlPermission
resource "aws_lambda_permission" "parser_url" {
  statement_id           = "ParserFunctionUrlPermission"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.parser.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# Logical ID: ParserFunctionInvokePermission
resource "aws_lambda_permission" "parser_invoke" {
  statement_id             = "ParserFunctionInvokePermission"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.parser.function_name
  principal                = "*"
  invoked_via_function_url = true
}
