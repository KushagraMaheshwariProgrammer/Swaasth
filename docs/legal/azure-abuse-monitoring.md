# Azure OpenAI — modified abuse monitoring (health data)

**Status:** Application draft. Submit via Azure AI Foundry / the current Microsoft “Limited Access” / modified abuse monitoring process.  
**Date:** 12 August 2026

## Why this is needed

Swaasth sends **patient document text** (bills, prescriptions, labs, discharge summaries) to Azure OpenAI. Default abuse monitoring can retain prompts and allow human review. That is a serious confidentiality issue for health data.

## What to request

1. **Modified content filtering / abuse monitoring exemption** (or the then-current equivalent) so prompts and completions containing health data are not retained for human review, except as required by law.
2. **Region pin:** create or move the Azure OpenAI resource to **South India** (or Central India if South India is unavailable). Record the resource name and endpoint in the password manager. Update `AZURE_OPENAI_ENDPOINT` in Container Apps secrets.
3. Confirm the resource is **not** used to train foundation models on our prompts.

## Current engineering controls

- `backend/app/services/azure_openai_client.py` does not log prompt/response bodies.
- Privacy Policy §7 discloses Azure OpenAI and states we do not permit training on public models.
- Reports are labelled “Generated with AI assistance — verify before relying.”

## Operator checklist

- [x] Azure OpenAI resource region = India — resource `swaasthbot`, location **southindia** (confirmed 12 August 2026)
- [ ] Exemption application submitted (date: _________)
- [ ] Exemption approved / denied (date: _________)
- [ ] DPA confirmed ([dpa-request-microsoft.md](dpa-request-microsoft.md))
- [ ] Privacy Policy §8 updated if the region or monitoring status changes
