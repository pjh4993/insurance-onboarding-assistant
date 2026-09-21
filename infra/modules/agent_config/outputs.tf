output "bucket_name" {
  value = aws_s3_bucket.this.id
}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "prefix" {
  value = var.prefix
}

# Depends on the seeded baseline, so a task definition that reads it is registered only once a bundle exists.
output "uri" {
  value      = "s3://${aws_s3_bucket.this.id}/${var.prefix}"
  depends_on = [aws_s3_object.baseline_config]
}
