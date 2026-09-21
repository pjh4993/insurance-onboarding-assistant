# One RDS PostgreSQL instance with three schemas (domain, catalog, checkpoint).
# The schemas themselves are created by the backend's Alembic migrations.

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.data_subnet_ids
  tags       = var.tags
}

resource "aws_db_parameter_group" "this" {
  name        = "${var.name}-pg16"
  family      = "postgres16"
  description = "${var.name}: TLS required"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.master_username

  # RDS generates and stores the master password in Secrets Manager,
  # encrypted with the CMK. Tasks receive it as PGPASSWORD.
  manage_master_user_password   = true
  master_user_secret_kms_key_id = var.kms_key_arn

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.rds_security_group_id]
  parameter_group_name   = aws_db_parameter_group.this.name
  publicly_accessible    = false

  backup_retention_period    = var.backup_retention_days
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.skip_final_snapshot
  final_snapshot_identifier  = var.skip_final_snapshot ? null : "${var.name}-final"
  copy_tags_to_snapshot      = true
  auto_minor_version_upgrade = true
  apply_immediately          = !var.multi_az

  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Application secrets (CMK-encrypted)
# ---------------------------------------------------------------------------

# 32 random bytes = 64 hex chars, the format the backend expects for AES-256.
# The value lands in Terraform state; the state bucket is encrypted and private.
resource "random_id" "checkpoint_aes_key" {
  byte_length = 32
}

resource "random_password" "session_hmac_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "checkpoint_aes_key" {
  name        = "${var.name}/checkpoint-aes-key"
  description = "AES-256 key (hex) for the encrypted LangGraph checkpoint serializer. Not rotated: see infrastructure.md section 3."
  kms_key_id  = var.kms_key_arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "checkpoint_aes_key" {
  secret_id     = aws_secretsmanager_secret.checkpoint_aes_key.id
  secret_string = random_id.checkpoint_aes_key.hex
}

resource "aws_secretsmanager_secret" "session_hmac_key" {
  name        = "${var.name}/session-hmac-key"
  description = "HMAC key for customer session-link tokens"
  kms_key_id  = var.kms_key_arn
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "session_hmac_key" {
  secret_id     = aws_secretsmanager_secret.session_hmac_key.id
  secret_string = random_password.session_hmac_key.result
}

# TODO(checkpoint-cleanup): the 30-day checkpoint cleanup is deferred
# (implementation-plan.md section 1). Design: an EventBridge Scheduler schedule
# runs a daily ECS task from the backend image with a cleanup command that deletes
# threads whose session last_activity_at is older than 30 days, via the
# checkpointer's delete_thread. Needs: aws_scheduler_schedule + a scheduler IAM
# role allowed to ecs:RunTask and iam:PassRole on the backend task/execution roles.
