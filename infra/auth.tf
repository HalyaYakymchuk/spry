# ==============================================================================
# Auth Infrastructure (Lab 4: Migrated from auth.yml / peach-auth)
# ==============================================================================

# Logical ID: UserPool
resource "aws_cognito_user_pool" "this" {
  name                     = "${var.auth_project_name}-user-pool"
  user_pool_tier           = "ESSENTIALS"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  password_policy {
    minimum_length    = 8
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
  }

  tags = {
    Project = var.auth_project_name
  }
}

# Logical ID: UserPoolIdentityProviderGoogle
resource "aws_cognito_identity_provider" "google" {
  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    username       = "sub"
  }

  lifecycle {
    ignore_changes = [provider_details]
  }
}

# Logical ID: UserPoolDomain
resource "aws_cognito_user_pool_domain" "this" {
  domain                = var.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.this.id
  managed_login_version = 2
}

# Logical ID: UserPoolClient
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.auth_project_name}-web-client"
  user_pool_id = aws_cognito_user_pool.this.id

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO", "Google"]

  callback_urls = [
    "https://${var.cloudfront_domain}",
    "https://${var.cloudfront_domain}/",
    "https://${var.cloudfront_domain}/auth/callback",
    "https://${var.cloudfront_domain}/auth/callback/",
    "http://localhost:${var.frontend_port}",
    "http://localhost:${var.frontend_port}/",
    "http://localhost:${var.frontend_port}/auth/callback",
    "http://localhost:${var.frontend_port}/auth/callback/"
  ]

  logout_urls = [
    "https://${var.cloudfront_domain}",
    "https://${var.cloudfront_domain}/",
    "http://localhost:${var.frontend_port}",
    "http://localhost:${var.frontend_port}/"
  ]

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_ADMIN_USER_PASSWORD_AUTH"
  ]

  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  lifecycle {
    ignore_changes = [generate_secret]
  }

  depends_on = [aws_cognito_identity_provider.google]
}

# Logical ID: ManagedLoginBranding
resource "aws_cognito_managed_login_branding" "this" {
  user_pool_id                = aws_cognito_user_pool.this.id
  client_id                   = aws_cognito_user_pool_client.web.id
  use_cognito_provided_values = true

  depends_on = [
    aws_cognito_user_pool_domain.this,
    aws_cognito_user_pool_client.web
  ]
}
