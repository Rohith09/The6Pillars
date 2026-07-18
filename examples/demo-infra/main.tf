terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# Deliberately flawed demo infra for `pillars review` — do not deploy as-is.

resource "aws_s3_bucket" "data" {
  bucket = "my-personal-project-data-bucket"
}

resource "aws_s3_bucket_acl" "data_acl" {
  bucket = aws_s3_bucket.data.id
  acl    = "public-read"
}

resource "aws_db_instance" "main" {
  identifier              = "my-app-db"
  engine                  = "postgres"
  engine_version          = "15.4"
  instance_class          = "db.t3.medium"
  allocated_storage       = 20
  db_name                 = "appdb"
  username                = "appadmin"
  password                = "changeme123!"
  multi_az                = false
  publicly_accessible     = false
  skip_final_snapshot     = true
  backup_retention_period = 0
  storage_encrypted       = false
  deletion_protection     = false
}
