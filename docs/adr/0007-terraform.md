# 7. Transition from CloudFormation to Terraform & HCP Terraform

* **Status:** Accepted
* **Date:** 2026-10-28

---

## Context
Previously, Spry's infrastructure was managed via individual, fragmented AWS CloudFormation templates (`cognito.yaml`, `reports.yml`, `parser.yaml`). Deployments relied on custom shell scripts (`deploy-backend.sh`) and raw AWS CLI commands executed across local environments and CI runners.

As the system grew (adding Bedrock-powered AI parsers, SQS report queues, and Cognito auth flows), CloudFormation templates became difficult to manage, lacked clear cross-resource modularity, and made drift detection and speculative previews complex. We needed a unified, declarative Infrastructure as Code (IaC) solution with automated remote CI/CD workflows.

---

## Decision
We migrated all core infrastructure resources to **HashiCorp Terraform** located in the `infra/` directory, using **HCP Terraform (Terraform Cloud)** as the remote execution backend and state store.

### Key Architectural Answers:

### 1. Why Terraform (and not CloudFormation, AWS CDK, or OpenTofu)?
* **vs. CloudFormation:** CloudFormation is AWS-locked, slow at rollbacks, and verbose. Its change sets lack the clarity of Terraform speculative plans on pull requests.
* **vs. AWS CDK:** While CDK offers imperative programming (TypeScript/Python), it compiles down to CloudFormation anyway, inheriting all CloudFormation synthesis and deployment limitations. For our scope, declarative HCL provides transparent, predictable infrastructure definition without the overhead of language SDK builds.
* **vs. OpenTofu:** While OpenTofu is fully open-source, HCP Terraform provides a turnkey managed SaaS execution environment, native VCS-driven workflows, free-tier remote speculative plans directly on GitHub PRs, and secure managed state locking without needing to self-host an orchestrator or configure manual DynamoDB locks.

### 2. Who can change the infrastructure now, and how?
* **No Direct / Local Applies:** Direct `terraform apply` is strictly forbidden locally and removed from developer workstations and the `Makefile`.
* **VCS-Driven Workflow:** Changes are made solely through Git:
  1. Developers create a branch and run `make infra-plan` for local syntax/plan preview.
  2. Opening a Pull Request triggers an automated **Speculative Plan** in HCP Terraform.
  3. Once peer-reviewed and merged into `main`, HCP Terraform automatically executes `terraform apply` in the cloud workspace (`spry-dev`).

### 3. Where do the secrets and state end up?
* **State Storage:** The `terraform.tfstate` is encrypted at rest and in transit inside **HCP Terraform**. It is never committed to Git and no longer resides on local developer disks.
* **Sensitive Credentials:** AWS credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are stored as **Sensitive Environment Variables** inside the HCP Terraform workspace. Developers and CI pipelines do not need long-lived AWS administrator keys stored locally.
* **Outputs:** Non-sensitive outputs are exposed via `infra/outputs.tf` and consumed locally or in application build pipelines via `make generate-env` (`terraform output -raw`).

### 4. What happens if HCP Terraform is down?
* **Production Continues Running:** Existing AWS infrastructure (Cognito, Lambdas, S3, SQS) runs independently inside AWS and is unaffected by an HCP Terraform outage.
* **Emergency Break-Glass Procedure:** If an urgent infrastructure fix is required while HCP Terraform is unavailable:
  1. An authorized maintainer can temporarily switch the backend configuration in `versions.tf` from `cloud {}` to a local backend or an emergency S3 backend.
  2. If an emergency fix is made directly in the AWS Management Console (hotfix), it introduces **drift**. Once HCP Terraform recovers, the team must immediately update the Terraform configuration files (`.tf`) to match the console change and run a plan to reconcile state without rolling back the emergency fix.

---

## Consequences

### Positive:
* Centralized, audited, and encrypted remote state with automatic state locking.
* Pull requests provide visibility into infrastructure changes before merging.
* Zero local credential sprawl for infrastructure provisioning.

### Negative / Trade-offs:
* Cloud provider migration requires learning HCL syntax and Terraform lifecycle quirks.
* Deployments strictly depend on remote pipeline execution; emergency fixes require strict reconciliation to avoid drift rollbacks.
