locals {
  az_count  = length(var.azs)
  nat_count = var.single_nat_gateway ? 1 : local.az_count

  # Interface endpoint ENIs go into the app subnets of the selected AZs only.
  endpoint_subnet_ids = [
    for i, az in var.azs : aws_subnet.app[i].id if contains(var.interface_endpoint_azs, az)
  ]
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = var.name })
}

# ---------------------------------------------------------------------------
# Subnets: public / private-app / private-data, one of each per AZ
# ---------------------------------------------------------------------------

resource "aws_subnet" "public" {
  count = local.az_count

  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = var.public_subnet_cidrs[count.index]

  tags = merge(var.tags, { Name = "${var.name}-public-${var.azs[count.index]}", Tier = "public" })
}

resource "aws_subnet" "app" {
  count = local.az_count

  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = var.app_subnet_cidrs[count.index]

  tags = merge(var.tags, { Name = "${var.name}-app-${var.azs[count.index]}", Tier = "private-app" })
}

resource "aws_subnet" "data" {
  count = local.az_count

  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[count.index]
  cidr_block        = var.data_subnet_cidrs[count.index]

  tags = merge(var.tags, { Name = "${var.name}-data-${var.azs[count.index]}", Tier = "private-data" })
}

# ---------------------------------------------------------------------------
# NAT: outbound internet only (Cognito / ALB signing keys, prod external systems)
# ---------------------------------------------------------------------------

resource "aws_eip" "nat" {
  count  = local.nat_count
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name}-nat-${var.azs[count.index]}" })
}

resource "aws_nat_gateway" "this" {
  count = local.nat_count

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags       = merge(var.tags, { Name = "${var.name}-nat-${var.azs[count.index]}" })
  depends_on = [aws_internet_gateway.this]
}

# ---------------------------------------------------------------------------
# Route tables
# ---------------------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-public" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = local.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "app" {
  count  = local.az_count
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-app-${var.azs[count.index]}" })
}

resource "aws_route" "app_nat" {
  count = local.az_count

  route_table_id         = aws_route_table.app[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  # Single NAT: every AZ uses NAT 0. Per-AZ NAT: each AZ uses its own.
  nat_gateway_id = aws_nat_gateway.this[min(count.index, local.nat_count - 1)].id
}

resource "aws_route_table_association" "app" {
  count          = local.az_count
  subnet_id      = aws_subnet.app[count.index].id
  route_table_id = aws_route_table.app[count.index].id
}

# Data tier: local routes only (plus the S3 gateway endpoint).
resource "aws_route_table" "data" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-data" })
}

resource "aws_route_table_association" "data" {
  count          = local.az_count
  subnet_id      = aws_subnet.data[count.index].id
  route_table_id = aws_route_table.data.id
}

# ---------------------------------------------------------------------------
# VPC endpoints
# ---------------------------------------------------------------------------

# Gateway endpoint: free, serves ECR image layers.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(aws_route_table.app[*].id, [aws_route_table.data.id])

  tags = merge(var.tags, { Name = "${var.name}-s3" })
}

# Security group for interface endpoints. Ingress rules (443 from the frontend,
# backend and mock task SGs) are added by the security module, which owns those SGs.
resource "aws_security_group" "endpoints" {
  name        = "${var.name}-endpoints"
  description = "Interface VPC endpoints: 443 from ECS task security groups"
  vpc_id      = aws_vpc.this.id

  tags = merge(var.tags, { Name = "${var.name}-endpoints" })
}

resource "aws_vpc_endpoint" "interface" {
  for_each = toset(var.interface_endpoint_services)

  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.endpoint_subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]

  tags = merge(var.tags, { Name = "${var.name}-${each.value}" })
}
