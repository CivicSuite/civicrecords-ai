# CivicRecords AI — User Manual

**For Municipal Records Staff**
Version 1.0.0 · April 2026

---

> This manual is written for you — the person sitting at a desk, answering records requests, and trying to get your work done. You do not need to be technical to use this software. If you can use a search engine, you can use CivicRecords AI.

---

## Table of Contents

1. [What is CivicRecords AI?](#1-what-is-civicrecords-ai)
2. [Getting Started](#2-getting-started)
3. [Onboarding Your City](#3-onboarding-your-city)
4. [City Profile](#4-city-profile)
5. [Searching Documents](#5-searching-documents)
6. [Managing Records Requests](#6-managing-records-requests)
7. [Reviewing and Approving Requests](#7-reviewing-and-approving-requests)
8. [Exemption Detection](#8-exemption-detection)
9. [Managing Data Sources](#9-managing-data-sources)
10. [User Management](#10-user-management)
11. [Discovery Dashboard (Preview)](#11-discovery-dashboard-preview)
12. [Troubleshooting](#12-troubleshooting)
13. [Glossary](#13-glossary)

---

## 1. What is CivicRecords AI?

When a resident, journalist, or attorney sends your office an open records request — asking for emails, contracts, meeting minutes, or other city documents — you have to find the right records, check them for sensitive information, and prepare a response. Depending on how many documents your city has, that search can take hours or days.

**CivicRecords AI is a search assistant that helps you do that work faster.**

Here is what it does in plain terms:

- It reads and indexes your city's documents — PDFs, Word files, spreadsheets, emails, and more — so you can search through all of them at once using plain English.
- When you get a records request, it helps you find the relevant documents quickly.
- It flags documents that might contain sensitive information (like Social Security numbers or personal data) that could be exempt from disclosure.
- It helps you track each request from the moment it arrives until the day you send the response, including any fees involved.
- It can generate a draft response letter for staff review before it goes out.
- It keeps a complete record of everything that happened — who searched for what, who made what decisions — so your office is protected if anyone ever questions your process.

**What it does not do:**

- It does not make decisions for you. Every exemption flag, every draft response, every document you include or exclude — you decide. The software is a helper, not a decision-maker.
- It does not send anything automatically. Nothing goes out the door without a human pressing a final "approve" button.
- It does not connect to the internet. Everything stays inside your city's network. No resident data ever leaves the building.
- It is not a replacement for your city attorney or your judgment.

Think of it as a very fast research assistant who has read every document your city has on file and is standing by to help you find things.

---

## 2. Getting Started

### Opening the Application

CivicRecords AI runs in your web browser — the same way you might use your city's email or an online form. You do not need to install anything on your computer.

Open your web browser (Chrome, Firefox, or Edge all work) and type the address your IT department gave you into the address bar. It will look something like:

```
http://civicrecords.cityname.gov
```

or

```
http://10.1.2.3:8080
```

Ask your IT department if you are not sure what address to use.

### Logging In

When you arrive at the login page, you will see the CivicRecords AI logo badge and two fields:

- **Email** — the email address your administrator set up for your account
- **Password** — the password you were given (you should change this to something personal on your first login)

Type your email and password, then click **Log In**.

If you see a message saying your credentials are incorrect, double-check that Caps Lock is not on. If you still cannot log in, see [Troubleshooting](#12-troubleshooting) or contact your administrator.

### Navigating the Application

After you log in, you will see the **sidebar** on the left side of every screen. This is your main navigation menu. It is organized into three groups:

**Workflow** — The day-to-day tools you use to process records requests:
- **Search** — Find documents across your city's indexed files
- **Requests** — Track and manage open records requests
- **Exemptions** — Review flagged content across all requests

**Setup** — Tools for connecting your city's data:
- **Data Sources** — Connect document folders and other integrations
- **Ingestion** — Monitor the document indexing process

**Administration** — Tools for managing the system (administrators only):
- **Users** — Create and manage user accounts
- **Settings** — Configure system-wide options

When you first land after logging in, the sidebar also shows summary cards with how many open requests are in progress, how many are approaching their deadline, and any items waiting for your attention.

The exact items you see in the sidebar depend on your role. If you are a standard staff member, you will not see the Administration group — those items are for administrators only.

---

## 3. Onboarding Your City

When CivicRecords AI is first set up for your city, an administrator will be guided through a brief onboarding wizard before anything else is available. If you are that administrator, this section explains what to expect.

### The Onboarding Wizard

The onboarding wizard walks you through three phases. Think of it as a short setup interview that helps the system understand your city before you start processing requests.

**Phase 1: City Profile**

You will enter basic information about your city:

- City name, state, and county
- Primary contact name and email for the records office
- The open records law your city operates under (for example, CORA for Colorado)
- Your statutory response deadline (for example, 7 business days)

This information appears on your City Profile page (see Section 4) and is used to calculate deadlines automatically.

**Phase 2: Systems**

You will identify what kinds of document systems your city uses:

- File servers or shared drives
- Email systems (Exchange, Gmail, etc.)
- Databases or case management software
- Any other places city records are stored

You do not connect these systems during this phase — you are just telling the system what exists. Connections are set up later in Data Sources (see Section 9).

**Phase 3: Gap Map**

Based on what you told the system in Phase 2, the wizard will generate a **Gap Map** — a visual summary of which systems are connected, which are not yet connected, and which are on the roadmap. This helps your office know at a glance whether your searches are comprehensive or whether certain document repositories are still missing from the system.

Once you complete all three phases, the wizard closes and you land on your City Profile page.

---

## 4. City Profile

The **City Profile** page is a permanent home for your city's key information. You can access it from the sidebar at any time. Administrators can edit it; staff members can view it.

### What the City Profile Shows

**City Details** — The basic information entered during onboarding: city name, state, county, contact, applicable open records law, and response deadline.

**Connected Systems** — A list of every document system that has been set up in Data Sources, with its current connection status (connected, error, not yet configured).

**Gap Map** — The same visual summary from onboarding, kept up to date as you add or remove data sources. Green items are connected. Gray items are identified but not yet connected. This is a quick reference for your records officers to understand what the system can and cannot search.

---

## 5. Searching Documents

The search screen is where you go to find documents. Click **Search** in the sidebar.

### How to Type a Query

You do not need to use special codes or exact phrases. Just type what you are looking for in plain English, the same way you would ask a question to a colleague.

**Examples of good queries:**

- `contracts with ABC Paving from 2023`
- `emails about the Main Street water line repair`
- `city council minutes mentioning the budget amendment`
- `police department use of force policy`

Type your query in the search box and press **Enter** or click the **Search** button.

### What Results Look Like

After a moment, you will see a list of results. Each result shows:

- **Document name** — the filename and where it came from
- **An excerpt** — a short passage from the document showing the part that matched your search, with the relevant words highlighted
- **A confidence score** — a number from 0 to 100 (sometimes shown as a percentage)
- **Source information** — the file path or folder where the document lives

You can click on any result to see more of that document.

### What the Confidence Score Means

The confidence score tells you how closely the system thinks that document matches your search. Think of it like a relevance rating:

- **80–100** — Very likely relevant. The document closely matches what you searched for.
- **50–79** — Possibly relevant. Worth looking at, but may or may not be what you need.
- **Below 50** — Less likely relevant. The system found some connection but it may be a stretch.

A high confidence score does not mean a document is definitely responsive to a records request — that is your judgment call. It just means the search engine thinks it is a strong match.

### Using Filters

On the right side of the search screen (or above the results, depending on your screen), you will see filter options. Filters help you narrow down results when you have too many.

- **Date range** — Only show documents from a certain time period (for example, "January 2022 to December 2023")
- **Department** — Only show documents from a specific department or folder
- **File type** — Only show PDFs, or only Word documents, etc.
- **Source** — If your city has multiple document collections, you can search just one

To use a filter, click on it and select your options. The results will update automatically.

### What "Generate AI Summary" Does

At the top of your search results, you may see a button that says **Generate AI Summary** or **Summarize Results**. When you click it, the system will read the top results and write a short paragraph summarizing what it found.

**This is a draft. It requires your review.**

The summary is generated by the AI and may not be perfectly accurate. It is a starting point to help you orient yourself — not a finished product. You should always read the actual documents before deciding whether they are responsive.

Every AI-generated summary will be clearly labeled: *"AI-generated draft requiring human review."* That label is there on purpose and cannot be removed.

### Refining Your Search

If your first search did not return what you were looking for, try:

- Using different words (for example, "road repair" instead of "street maintenance")
- Being more specific ("Miller Park playground equipment purchase 2022" instead of "playground")
- Being less specific if you got zero results
- Adjusting the date filter if the document might be older or newer than you expected

You can also ask follow-up questions in the search box to refine results within the same session.

---

## 6. Managing Records Requests

The **Requests** screen is where you track every open records request your office receives. Click **Requests** in the sidebar.

### Creating a New Request

When a new records request arrives (by mail, email, fax, or in person), you need to log it in the system right away. Click the **New Request** button (usually in the upper right corner of the Requests screen).

You will see a form with the following fields:

**Requester Name** — The full name of the person or organization making the request. This is required.

**Requester Email** — Their email address, if you have it. This is used for communications.

**Date Received** — The date the request arrived at your office. This is important because your statutory deadline is calculated from this date.

**Statutory Deadline** — The date by which you must respond. Your IT administrator may have pre-configured this to calculate automatically based on your state's law (for example, 7 business days in some states, 10 in others). If it does not calculate automatically, enter the deadline by hand.

**Description** — A summary of what the requester is asking for. You can paste in the exact language from their request. Be thorough — this description is what you will use to guide your search.

Click **Save** or **Create Request** when you are done. The request is now in the system with a status of **Received**.

### What the Fields Mean

| Field | What it's for |
|---|---|
| Requester Name | Identifies who made the request for your records |
| Requester Email | How to contact them with your response |
| Date Received | Starts your legal clock for response deadlines |
| Statutory Deadline | The date you must respond by under state law |
| Description | What records they are asking for |
| Assigned To | Which staff member is handling this request |

### How the Status Workflow Works

Every request moves through a series of stages. You can see the current status on each request card. Here is what each status means:

**Received** — You have logged the request but have not started searching yet. The clock is running.

**Clarification Needed** — The request is unclear or too broad to search effectively. You need more information from the requester before you can proceed. Use this status when you are waiting on a reply from them.

**Assigned** — The request has been assigned to a specific staff member who will handle it.

**Searching** — You are actively searching for responsive documents. Change the status to this when you start your search work.

**In Review** — You have found documents and are reviewing them to decide what to include, what to exclude, and whether any exemptions apply.

**Drafted** — You have prepared a draft response letter and it is ready for supervisor review.

**Approved** — A supervisor has reviewed and approved the response.

**Ready for Release** — The response has been approved and is queued to go out.

**Sent** — The response has been sent to the requester.

**Fulfilled** — The requester has confirmed they received everything they needed. The request is complete.

**Closed** — The request has been closed without fulfillment (for example, the requester withdrew it, or the request was denied and the appeal period has passed).

To move a request from one status to the next, open the request and look for the **Update Status** button or a dropdown menu showing the current status. Select the next status and click **Save**.

Moving a request backward (for example, from "Drafted" back to "In Review") is also possible if you need to make changes.

### The Request Detail View

When you open a request, you will see the main details at the top, followed by three tabbed sections:

**Timeline** — A chronological log of every action taken on this request: when it was created, when the status changed, when documents were attached, when flags were reviewed, and any notes added along the way. This is your complete audit trail for this request.

**Messages** — A running log of communications related to this request. If you sent a clarification question to the requester, or a note to your supervisor, it is recorded here. Messages are internal unless explicitly marked otherwise.

**Fees** — A record of any fees assessed for this request. Many states allow governments to charge for the cost of searching and copying records. You can log fee amounts here, note whether they have been collected, and attach receipts or fee waiver decisions.

### Attaching Documents from Search

When you find a document in your search that is responsive to a specific request, you can attach it directly to that request.

**Here is how:**

1. Open the request you are working on.
2. Click **Search for Documents** (inside the request screen). This opens a search panel connected to this request.
3. Run your search the same way as described in Section 5.
4. When you find a relevant document, click **Attach to Request** next to that result.
5. You will be asked to enter a short note about why this document is relevant (for example: "This is the contract referenced in the requester's description"). Enter your note and click **Attach**.

The document now appears in the **Attached Documents** list on the request. You can mark each attached document as:

- **Included** — You intend to release this document
- **Excluded** — You are not releasing this document (and you should note why)
- **Pending** — You have not decided yet

### Generating a Response Letter

When you are ready to prepare your formal response, click **Generate Response Letter** on the request. The system will draft a letter based on:

- The requester's name and contact information
- What they asked for
- Which documents you are including or excluding
- Any exemptions that were accepted

**This is a draft. Review it carefully before submitting.**

The letter will be labeled as AI-generated and must be reviewed by a staff member before the request can advance to supervisor review. You can edit the letter directly on screen. Common things to check: make sure the tone is professional, confirm that exclusions are explained correctly, and verify the deadline language is accurate for your state.

### Tracking Fees

If your city charges for records requests, use the **Fees** tab on each request to track what was assessed and what was collected.

To add a fee:

1. Open the request and click the **Fees** tab.
2. Click **Add Fee**.
3. Enter the amount, the reason (for example, "Search time: 2 hours at $15/hr" or "Copying: 47 pages at $0.25/page"), and the date assessed.
4. Click **Save**.

You can also record fee waivers here if the requester qualified for one (for example, media exemptions or indigency waivers). Log the reason for the waiver so it is part of the permanent record.

### Submitting for Review

When you are satisfied with the documents you have gathered, the fees are logged, the response letter is drafted, and any exemption decisions are made (see Section 8), you are ready to submit the request for supervisor review.

1. Make sure the request status is **In Review** or **Drafted**.
2. Open the request.
3. Click **Submit for Review**.
4. Add any notes you want the reviewer to see (for example, "I excluded the HR file because of the personnel exemption — see flag #3").
5. Click **Submit**.

The request will move to **Drafted** status and appear in your supervisor's review queue.

---

## 7. Reviewing and Approving Requests

This section is for supervisors, department heads, and city attorneys who review staff work before responses go out.

### How to See Requests Awaiting Review

When you log in, your dashboard will show a count of requests waiting for your review. You can also click **Requests** in the sidebar and filter by status: select **Drafted** from the status filter to see only requests that need your attention.

Each request card shows:
- The requester's name
- What they are asking for
- The deadline
- Who prepared the response
- Any notes from the staff member

### Reviewing a Request

Click on a request to open it. You will see:

- The full description of what was requested
- All attached documents, marked as included, excluded, or pending
- Any exemption flags that were reviewed (see Section 8)
- The draft response letter (if one was generated)
- Notes from the staff member who prepared it
- The Timeline showing the full history of the request
- Any fees assessed on the Fees tab

Take your time reviewing each attached document. You can click on a document to view it or the relevant excerpt. Check that:

- The right documents are included
- Anything excluded has a valid reason
- Exemption flags were reviewed properly
- The response letter (if any) is accurate
- Fees (if any) are correctly documented

### How to Approve

If everything looks correct, click the **Approve** button. You may be asked to enter a brief note confirming your approval (for example, "Reviewed and approved — all exemptions properly noted"). Click **Confirm Approval**.

The request status will change to **Approved**, then to **Ready for Release**. The staff member will be notified. The final step — marking it as **Sent** — happens after the response is actually delivered to the requester.

### How to Reject (Send Back for Revision)

If you find a problem — a missing document, an exemption that was not flagged, or a response letter that needs changes — click **Request Revision** (or **Reject**).

You must enter **review notes** explaining what needs to be fixed. Be specific: "Please re-check the 2022 folder for contract amendments" is more helpful than "needs more work."

The request will move back to **In Review** status and the staff member will see your notes.

### What Review Notes Are

Review notes are the written explanation a reviewer leaves when sending a request back for revision. They are:

- Required whenever you reject or request changes
- Visible to the staff member who prepared the response
- Permanently logged in the audit trail
- Your way of communicating exactly what needs to change

Think of them as the sticky note you would leave on a paper file — except this one is saved forever.

---

## 8. Exemption Detection

### What Exemptions Are

Not every document in a city's files can be released to the public. State law (FOIA, CORA, and their equivalents) defines categories of information that are protected. These are called **exemptions**.

Common examples:
- Personal information (like Social Security numbers or medical records)
- Personnel files (employee evaluations, disciplinary records)
- Active law enforcement investigations
- Attorney-client privileged communications
- Certain financial records and trade secrets

When you respond to a records request, you have to check whether any of the responsive documents contain exempt information. If they do, you may need to redact (black out) that information or withhold the document entirely. That decision is always yours — and usually needs your city attorney's input for anything complicated.

### How the System Flags Potential Exemptions

CivicRecords AI has a built-in system that automatically scans documents for content that might be exempt. When it finds something, it creates an **exemption flag**.

Flags are not decisions. They are the system's way of saying: *"Hey, you should look at this part of this document."*

You will see flags appear:
- On the document view (highlighted passages)
- On the request page, in an "Exemption Flags" section
- In the **Exemptions** section of the sidebar

Each flag shows:
- What triggered it (for example, "SSN pattern detected" or "personnel file keyword")
- The exact text that was flagged
- A confidence level
- The document and page where it was found

### The Exemptions Screen: Two Tabs

When you click **Exemptions** in the sidebar, you will see a tabbed interface with two views:

**Rules** — A list of all the exemption detection rules configured in your system. Each rule shows its name, category, description, and how many flags it has generated. Administrators can edit or add rules from this tab.

**Flags for Review** — All exemption flags that currently need a human decision, across all requests. You can filter this list by request, by flag category, or by flag status. This is the queue you work through when reviewing exemptions.

### How to Review Flags

To review a flag, open the request or go to the **Exemptions** screen and click the **Flags for Review** tab. For each flag, you have two choices:

**Accept** — You agree that this content is potentially exempt and you will take that into account (redact it, withhold the document, or note it in your response). Click **Accept Flag**.

**Reject** — You reviewed the flagged content and determined it is not actually exempt (for example, a Social Security number that turned out to be a permit number formatted similarly). Click **Reject Flag** and enter a brief note explaining why.

You must take an action on every flag before a request can be submitted for review. No flag can be left in "flagged" status — the system requires a human decision on each one.

All flag decisions are logged permanently in the audit trail.

### What the Built-In Rules Catch

The system comes with automatic detection rules for common categories of sensitive information. These rules scan for patterns in the text of your documents.

**PII (Personally Identifiable Information) rules:**

- **Social Security Numbers** — Detects 9-digit numbers in formats like `XXX-XX-XXXX` or `XXXXXXXXX`
- **Phone numbers** — Detects phone number patterns in documents
- **Email addresses** — Detects email addresses that may identify private individuals

**Statutory phrase detection:**

- Keywords associated with personnel matters
- Keywords associated with law enforcement investigation exemptions
- Attorney-client privilege markers
- Other state-specific statutory phrases (configured by your administrator)

The LLM (AI language model) also does a secondary pass to catch things the rules might miss, and may flag passages that look legally sensitive even if they do not match a specific pattern.

### What the Acceptance Rate Dashboard Shows

In the **Exemptions** section of the sidebar, administrators and supervisors can see a dashboard that shows how exemption flags are being handled across all requests.

It shows:
- How many flags were generated vs. how many were accepted or rejected
- Breakdown by flag category (PII, personnel, law enforcement, etc.)
- Trends over time
- Which rules are generating the most flags

This helps your office understand whether the detection rules are well-calibrated. If a particular rule is flagging things too aggressively (most flags get rejected), your administrator can adjust it. If too few flags are accepted, the rules may not be sensitive enough.

---

## 9. Managing Data Sources

This section is primarily for administrators and IT staff, but records officers may also use it to connect new document folders.

### What a Data Source Is

A data source is any collection of documents you want CivicRecords AI to search through. Each data source is shown as a **card** on the Data Sources page, making it easy to see everything at a glance and check the status of each connection.

### Types of Data Sources

The system supports connecting different types of document repositories. Each source card shows its type and integration status:

- **File Directory** — Folders or shared drives on your city's file server. This is the most common source type and is available now.
- **Email** — City email systems (Exchange, Google Workspace, etc.). On the integration roadmap for a future release.
- **Database** — Structured databases or case management systems. On the integration roadmap for a future release.
- **API** — External systems that provide a data API. On the integration roadmap for a future release.

Cards for future integrations will show a "Coming Soon" or "Roadmap" badge so you can see what is planned without being able to accidentally configure something that is not yet available.

### How to Add a Document Directory

1. Click **Data Sources** in the sidebar.
2. Click **Add Data Source**.
3. Fill in the form:
   - **Name** — A friendly name for this source (for example: "City Clerk Archives 2015–2023")
   - **Type** — Select "File Directory"
   - **Path** — The folder path on the server (your IT person will give you this, for example: `\\fileserver\cityrecords\clerk`)
   - **Schedule** — How often to check for new or changed documents (for example, "Every night at midnight")
4. Click **Save**.

The system will add this source to its list. The first time it runs, it will read and index every document in that folder. This can take a while depending on how many documents there are.

### How to Trigger Ingestion

Normally, ingestion (the process of reading and indexing documents) runs on the schedule you set. But if you just added new documents and want the system to pick them up right away, you can trigger it manually:

1. Go to **Data Sources**.
2. Find the source card you want to update.
3. Click **Run Now** (or **Trigger Ingestion**) on that card.

The system will start processing in the background. You do not need to wait on the page — you can navigate away and check back later.

### What the Ingestion Dashboard Shows

Click **Ingestion** in the sidebar to see the ingestion monitor. For each source, you will see:

- **Status** — Running, Completed, Queued, or Error
- **Last run** — Shown as a relative timestamp (for example, "2 hours ago" or "Yesterday at 11:45 PM")
- **Documents processed** — How many files were read
- **New documents** — How many new files were found since last run
- **Errors** — Any files the system could not read, and why

Document filenames in the ingestion log are shown as their original, readable names — you will not see technical IDs or system-generated prefixes in the file list.

If you see errors, note the file names and pass them to your IT department. Common causes are password-protected files, corrupted files, or file types the system cannot read.

The dashboard also shows the overall health of your knowledge base: how many documents are indexed in total and when the last full ingestion ran.

---

## 10. User Management

This section is for administrators only.

### How to Create New Users

1. Click **Users** in the sidebar (only visible to administrators).
2. Click **Add User**.
3. A dialog will appear. Fill in:
   - **Full Name**
   - **Email Address** — This is their login username
   - **Role** — Choose from the four roles described below
4. Click **Create User**.

The new user will receive an email (if your system is configured for email) or you will need to share their temporary password with them directly. They should change their password on first login.

### What the Four Roles Mean

**Admin**
The administrator can do everything: manage users, configure data sources, adjust exemption rules, view all requests, and change system settings. This role should be given to your IT administrator and possibly your records officer. There should be very few admins.

**Staff**
The standard role for records clerks and the people who handle day-to-day request work. Staff can search documents, create and manage requests, attach documents, review exemption flags, and submit requests for supervisor review. They cannot manage users or change system configuration.

**Reviewer**
For supervisors, department heads, and city attorneys who review completed requests before responses go out. Reviewers can see all requests in the "Drafted" queue, approve or reject them, and add review notes. They can also search documents. They cannot create requests or manage users.

**Read-Only**
For people who need to be able to look at the system but should not be able to change anything. Useful for auditors, oversight staff, or elected officials who want visibility without the ability to accidentally modify a request.

| Can do this | Admin | Staff | Reviewer | Read-Only |
|---|---|---|---|---|
| Search documents | Yes | Yes | Yes | Yes |
| View requests | Yes | Yes | Yes | Yes |
| Create/edit requests | Yes | Yes | No | No |
| Submit for review | Yes | Yes | No | No |
| Approve/reject requests | Yes | No | Yes | No |
| Review exemption flags | Yes | Yes | Yes | No |
| Manage data sources | Yes | No | No | No |
| Manage users | Yes | No | No | No |
| Change system settings | Yes | No | No | No |

---

## 11. Discovery Dashboard (Preview)

The **Discovery Dashboard** is a feature coming in v1.1. When it arrives, it will give records officers a proactive intelligence view of your document collection — surfacing patterns, flagging topics that frequently appear in requests, and helping your office get ahead of records issues before requests arrive.

In v1.0.0, you may see a preview card or placeholder for this section. No data is displayed yet — this is a look at what is coming.

If you have ideas for what you would like to see in the Discovery Dashboard, share them with your CivicRecords AI administrator. The development team welcomes feedback from the people who use the system every day.

---

## 12. Troubleshooting

### "I can't log in"

**Check first:**
- Is Caps Lock on? Passwords are case-sensitive.
- Are you using the right email address? Try the full email, not just your first name.
- Is the address in your browser correct? Check with IT if you are unsure.

**If you still cannot log in:**
Contact your CivicRecords AI administrator. They can reset your password. If your administrator is also locked out, contact your IT department — they can reset accounts directly on the server.

You cannot reset your own password from the login screen in the current version. Your administrator must do it for you.

---

### "Search returns no results"

**Possible reasons:**

1. **The documents have not been ingested yet.** If your IT department just set up the system or added a new folder, the indexing process may not have run yet. Go to Data Sources and check the ingestion status. If it shows "Never run" or "Queued," ask your IT person to trigger ingestion.

2. **Try different search terms.** The system searches meaning, not just exact words. If you searched "road maintenance contract" try also "street repair agreement" or "paving services."

3. **Your filters may be too narrow.** If you set a date range or department filter, try removing it and searching again.

4. **The document type may not be supported.** Some files — like password-protected PDFs or certain older formats — cannot be indexed. Ask IT to check the ingestion error log for that data source.

5. **The document may simply not exist** in the ingested sources. The system can only find what it has been given access to.

---

### "Ingestion is stuck"

If you go to Data Sources and a source shows "Running" for a very long time (more than a few hours for a normal-sized folder), something may have gone wrong.

**What to do:**
1. Note the data source name and when it started running.
2. Contact your IT department.
3. Tell them: "The ingestion for [source name] has been running since [time] and does not seem to be finishing."

IT will check the worker logs and can restart the process if needed. Do not try to click "Run Now" again while it shows "Running" — wait for IT to investigate first.

---

### "I see 'Bad Gateway' or a blank screen"

This means the application server is not responding. This is not something you caused — it is a server issue.

**What to do:**
1. Wait 30 seconds and refresh the page.
2. If it is still showing the error, try logging out and back in.
3. If it persists, contact your IT department and tell them: "CivicRecords AI is showing a Bad Gateway error."

IT will need to check whether the backend services are running. The fix usually involves restarting the application, which takes a few minutes.

---

## 13. Glossary

**Open Records Request**
A formal written request from a member of the public asking your government office to provide copies of specific records. State laws require governments to respond within a set time period and to release records unless a specific exemption applies.

**FOIA (Freedom of Information Act)**
The federal law that gives the public the right to request records from federal government agencies. Many states have their own equivalent laws (like Colorado's CORA). The term "FOIA" is often used informally to refer to any open records request, even at the local level.

**CORA (Colorado Open Records Act)**
Colorado's state open records law. CivicRecords AI is designed to the CORA standard, which is one of the strictest in the country — meaning if it works correctly under CORA, it works for most other states too.

**Exemption**
A category of information that state law says the government does not have to (or sometimes must not) release. Common examples: personnel files, medical records, ongoing criminal investigations, attorney-client privileged communications, and Social Security numbers. Exemptions vary by state. Your city attorney is the authority on which exemptions apply in your situation.

**Redaction**
The process of blacking out or removing specific text from a document before releasing it. For example, if a document contains an employee's Social Security number but everything else is releasable, you would redact (cover) just that number before sending the document to the requester. CivicRecords AI helps you identify what might need redaction, but the actual redacting is done by your staff.

**Ingestion**
The process by which CivicRecords AI reads your documents and prepares them to be searched. During ingestion, the system opens each file, extracts the text, breaks it into pieces, and stores it in a way that makes fast searching possible. Think of it like a librarian cataloging every book in a library so you can find things quickly.

**Chunking**
During ingestion, each document is broken into smaller pieces called "chunks." This is necessary because the AI works better with smaller pieces of text than with entire 50-page contracts. When you search, the system finds the relevant chunk and shows you where in the document it came from.

**Embedding**
After chunking, each piece of text is converted into a set of numbers that represents its meaning. These numbers are called an "embedding." The embedding lets the system compare meanings rather than just matching exact words. That is why you can search for "road maintenance" and find a document that says "street repair" — the meanings are similar even if the words are different.

**Vector Search**
The search method that uses embeddings to find documents by meaning. When you type a query, the system converts your query into an embedding and looks for document chunks with similar embeddings. This is different from a regular keyword search (which only finds exact words). CivicRecords AI uses both methods together for better results.

**PII (Personally Identifiable Information)**
Any information that can identify a specific person. Examples: a person's name combined with their address, Social Security numbers, driver's license numbers, medical record numbers, and financial account numbers. Many exemptions in open records law are designed to protect PII. CivicRecords AI has built-in rules to automatically flag common PII patterns like SSNs and phone numbers.

**Audit Log**
A permanent, tamper-evident record of everything that has happened in the system. Every search, every request update, every exemption decision, every login — all of it is recorded with a timestamp and the name of the person who did it. The audit log exists because open records laws require governments to be accountable for how they process records requests. You may be asked to produce the audit log if your office's process is ever questioned.

**Gap Map**
A visual summary of which document systems your city has connected to CivicRecords AI and which are not yet connected. The Gap Map helps records officers understand whether their searches are comprehensive and shows what is on the roadmap for future integration.

**Response Letter**
A formal letter generated by the system as a draft for staff review. The letter summarizes what the requester asked for, what is being provided, what (if anything) is being withheld, and the legal basis for any withholding. Staff must review and approve the letter before it is sent.

---

*CivicRecords AI is open-source software licensed under Apache 2.0. For technical documentation, installation instructions, and developer guides, see the project repository.*

*This manual covers version 1.0.0 of the system. If you are using a newer version and something does not match what you see on screen, check with your administrator for an updated manual.*
