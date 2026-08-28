variable "github_llvm_org_token" {
  description = "Token for updating github settings"
  type = string
  sensitive = true
  # Only allow fine-grained access tokens since the classic tokens have
  # very coarse grained permissions and we want to ensure the scope
  # of the tokens we use is limited as much as possible.
  # TODO: Only allow fine-grained access tokens with the minimum required permissions.
  validation {
    condition = startswith(var.github_llvm_org_token, "github_pat_")
    error_message = "Please use a fine-grained access token"
  }
}

provider "github" {
  owner = "llvm"
  # Use a fine-grained token with the permissions:
  # * Organization Self-Hosted Runners: read/write
  token = var.github_llvm_org_token
}

resource "github_repository" "llvm-project" {
  name = "llvm-project"
  allow_merge_commit = false
  allow_rebase_merge = false
  allow_squash_merge = true
  description = "The LLVM Project is a collection of modular and reusable compiler and toolchain technologies."
  has_issues = true
  homepage_url = "http://llvm.org"
  # Prevent accidentally deleteion of the repository.
  archive_on_destroy = true
  

  # Configure the lifecycle with multiple safeguards to prevent the repository
  # from being deleted.
  lifecycle {
    ignore_changes = all
    prevent_destroy = true
  }
}

import {
  to = github_repository.llvm-project
  id = "llvm-project"
}

resource "github_actions_runner_group" "llvm-premerge-cluster-us-central" {
  name = "llvm-premerge-cluster-us-central"
  visibility = "selected"
  allows_public_repositories = true
  restricted_to_workflows = false
  selected_repository_ids = [github_repository.llvm-project.repo_id]
}

import {
  to = github_actions_runner_group.llvm-premerge-cluster-us-central
  id = 63
}
