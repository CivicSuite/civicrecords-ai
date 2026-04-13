# Data Residency Attestation

**{{CITY_NAME}}, {{STATE}}**
**Date: {{EFFECTIVE_DATE}}**

---

## Attestation of Local Data Residency for CivicRecords AI

I, {{CONTACT_NAME}}, {{CONTACT_TITLE}} of {{CITY_NAME}}, {{STATE}}, hereby attest to the following facts regarding the deployment and operation of CivicRecords AI within {{CITY_NAME}}'s infrastructure.

## 1. Attestation Statements

### 1.1 Local Deployment

CivicRecords AI is installed and operates exclusively on server hardware owned by {{CITY_NAME}} and physically located at:

**{{FACILITY_ADDRESS}}**

The system is administered by {{CITY_NAME}} IT staff. No third party has physical or remote administrative access to the server unless explicitly authorized by {{CONTACT_NAME}} for a documented maintenance purpose.

### 1.2 No Cloud Services

CivicRecords AI does not use, connect to, or depend on any cloud computing services, including but not limited to:

- Cloud-hosted databases or storage (e.g., AWS S3, Azure Blob, Google Cloud Storage)
- Cloud-hosted AI/ML inference APIs (e.g., OpenAI API, Azure AI, Google Vertex AI, AWS Bedrock)
- Cloud-hosted application platforms (e.g., Heroku, Vercel, Azure App Service)
- Cloud-hosted search or analytics services

All application components — the web server, database, AI models, document storage, and search indices — run on locally hosted infrastructure described in Section 3 below.

### 1.3 No Telemetry or External Data Transmission

CivicRecords AI does not transmit any data to external servers, services, or endpoints. Specifically:

- No usage analytics or telemetry data is collected or transmitted.
- No crash reports or error logs are sent to external services.
- No document content, metadata, or user information is transmitted outside {{CITY_NAME}}'s network.
- No DNS, NTP, or other protocol-level communications are made to vendor-operated servers beyond standard OS-level services controlled by {{CITY_NAME}} IT.
- The application does not phone home, check for updates externally, or communicate with any CivicRecords AI project infrastructure.

### 1.4 Local AI Models

All artificial intelligence and machine learning models used by CivicRecords AI operate locally:

- Model weights are stored on {{CITY_NAME}}'s servers.
- All inference (AI processing) occurs on {{CITY_NAME}}'s hardware.
- No data is sent to external APIs for AI processing.
- Models are not updated, fine-tuned, or retrained using external services.
- Model updates, if any, are performed manually by {{CITY_NAME}} IT staff through a controlled process.

### 1.5 Verification

{{CITY_NAME}} has verified the above attestation statements through the following methods:

- **Network audit:** Reviewed firewall logs and network traffic to confirm no external data transmission from the CivicRecords AI server. Date of last audit: {{LAST_AUDIT_DATE}}
- **Source code review:** Confirmed that the deployed version of CivicRecords AI contains no external API calls, telemetry code, or cloud service integrations.
- **Configuration review:** Verified that application configuration files contain no external URLs, API keys, or cloud service credentials.
- **Physical inspection:** Confirmed server hardware is located at the attested facility address and is physically secured.

## 2. Data Categories and Storage Locations

| Data Category | Storage Location | Encryption | Access Control |
|---|---|---|---|
| Municipal documents | Local file system / local database | {{ENCRYPTION_AT_REST}} | Role-based; staff credentials |
| Records request data | Local PostgreSQL database | {{ENCRYPTION_AT_REST}} | Role-based; staff credentials |
| Requester contact info | Local PostgreSQL database | {{ENCRYPTION_AT_REST}} | Role-based; staff credentials |
| AI model weights | Local file system | N/A (non-sensitive) | OS-level file permissions |
| Application logs | Local file system | {{ENCRYPTION_AT_REST}} | IT administrator access |
| Audit trail | Local PostgreSQL database | {{ENCRYPTION_AT_REST}} | Read-only for non-admin staff |
| Backups | {{BACKUP_LOCATION}} | {{BACKUP_ENCRYPTION}} | IT administrator access |

## 3. Hardware Specifications

The following hardware is used to host CivicRecords AI:

| Component | Specification |
|---|---|
| Server Location | {{FACILITY_ADDRESS}} |
| Operating System | {{SERVER_OS}} |
| Processor | {{SERVER_CPU}} |
| Memory (RAM) | {{SERVER_RAM}} |
| Storage | {{SERVER_STORAGE}} |
| Network | {{NETWORK_CONFIG}} |
| UPS / Power Backup | {{POWER_BACKUP}} |

### Physical Security

- Server is located in: {{SERVER_ROOM_DESCRIPTION}}
- Physical access is restricted to: {{PHYSICAL_ACCESS_LIST}}
- Environmental controls: {{ENVIRONMENTAL_CONTROLS}}

## 4. Signature Block

I attest that the information provided in this document is true and accurate to the best of my knowledge as of the date signed.

**Primary Attestor:**

Name: {{CONTACT_NAME}}
Title: {{CONTACT_TITLE}}
Department: {{DEPARTMENT}}
Date: {{EFFECTIVE_DATE}}

Signature: ___________________________

---

**Reviewing Authority:**

Name: {{REVIEWER_NAME}}
Title: {{REVIEWER_TITLE}}
Date: _______________

Signature: ___________________________

---

**City Attorney Acknowledgment (Optional):**

Name: {{ATTORNEY_NAME}}
Title: City Attorney, {{CITY_NAME}}
Date: _______________

Signature: ___________________________

---

> **Disclaimer:** Consult your city attorney before adoption. This attestation template is a starting point. Your jurisdiction may have additional data residency, security, or compliance requirements that should be incorporated.

Template provided by CivicRecords AI (Apache 2.0).
