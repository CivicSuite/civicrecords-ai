--
-- PostgreSQL database dump
--

\restrict TpzmFDtyaibtowKM0WiehKumAMSgl4LOw1DpKHsXzWC4AXlEOHxqI5DxqSE3rhR

-- Dumped from database version 17.9 (Debian 17.9-1.pgdg12+1)
-- Dumped by pg_dump version 17.9 (Debian 17.9-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: flag_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.flag_status AS ENUM (
    'flagged',
    'reviewed',
    'accepted',
    'rejected'
);


--
-- Name: inclusion_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.inclusion_status AS ENUM (
    'included',
    'excluded',
    'pending'
);


--
-- Name: ingestion_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ingestion_status AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed'
);


--
-- Name: request_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.request_status AS ENUM (
    'received',
    'clarification_needed',
    'assigned',
    'searching',
    'in_review',
    'ready_for_release',
    'drafted',
    'approved',
    'fulfilled',
    'closed'
);


--
-- Name: rule_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rule_type AS ENUM (
    'regex',
    'keyword',
    'llm_prompt'
);


--
-- Name: source_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.source_type AS ENUM (
    'manual_drop',
    'file_system',
    'rest_api',
    'odbc'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'admin',
    'staff',
    'reviewer',
    'read_only',
    'liaison',
    'public'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _migration_015_report; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._migration_015_report (
    id integer NOT NULL,
    source_id character varying(36) NOT NULL,
    source_name character varying(255),
    schedule_minutes integer,
    action character varying(20),
    cron_expression character varying(50),
    note text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: _migration_015_report_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public._migration_015_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: _migration_015_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public._migration_015_report_id_seq OWNED BY public._migration_015_report.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    prev_hash character varying(64) DEFAULT '0000000000000000000000000000000000000000000000000000000000000000'::character varying NOT NULL,
    entry_hash character varying(64) NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    user_id uuid,
    action character varying(100) NOT NULL,
    resource_type character varying(100) NOT NULL,
    resource_id character varying(255),
    details jsonb,
    ai_generated boolean DEFAULT false NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: city_profile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.city_profile (
    id uuid NOT NULL,
    city_name character varying(200) NOT NULL,
    state character varying(2),
    county character varying(200),
    population_band character varying(50),
    email_platform character varying(50),
    has_dedicated_it boolean,
    monthly_request_volume character varying(20),
    onboarding_status character varying(20) NOT NULL,
    profile_data jsonb NOT NULL,
    gap_map jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by uuid
);


--
-- Name: connector_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connector_templates (
    id integer NOT NULL,
    vendor_name character varying(200) NOT NULL,
    protocol character varying(50) NOT NULL,
    auth_method character varying(50) NOT NULL,
    config_schema jsonb NOT NULL,
    default_sync_schedule character varying(50),
    default_rate_limit integer,
    redaction_tier integer NOT NULL,
    setup_instructions text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    catalog_version character varying(20) NOT NULL
);


--
-- Name: connector_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.connector_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: connector_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.connector_templates_id_seq OWNED BY public.connector_templates.id;


--
-- Name: data_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.data_sources (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    source_type public.source_type NOT NULL,
    connection_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    last_ingestion_at timestamp with time zone,
    discovered_source_id uuid,
    connector_template_id integer,
    sync_schedule character varying(50),
    last_sync_at timestamp with time zone,
    last_sync_status character varying(20),
    health_status character varying(20),
    schema_hash character varying(64),
    last_sync_cursor character varying,
    schedule_enabled boolean DEFAULT true NOT NULL,
    consecutive_failure_count integer DEFAULT 0 NOT NULL,
    last_error_message character varying(500),
    last_error_at timestamp with time zone,
    sync_paused boolean DEFAULT false NOT NULL,
    sync_paused_at timestamp with time zone,
    sync_paused_reason character varying(200),
    retry_batch_size integer,
    retry_time_limit_seconds integer,
    CONSTRAINT chk_sync_schedule_nonempty CHECK (((sync_schedule IS NULL) OR (length(TRIM(BOTH FROM sync_schedule)) > 0)))
);


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    id uuid NOT NULL,
    name character varying(200) NOT NULL,
    code character varying(20) NOT NULL,
    contact_email character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: disclosure_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disclosure_templates (
    id uuid NOT NULL,
    template_type character varying(100) NOT NULL,
    state_code character varying(2),
    content text NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    updated_by uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: document_cache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_cache (
    id uuid NOT NULL,
    document_id uuid NOT NULL,
    request_id uuid NOT NULL,
    cached_file_path text NOT NULL,
    file_size integer DEFAULT 0 NOT NULL,
    cached_at timestamp with time zone DEFAULT now()
);


--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_chunks (
    id uuid NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content_text text NOT NULL,
    embedding public.vector(768),
    token_count integer DEFAULT 0 NOT NULL,
    page_number integer,
    content_tsvector tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, content_text)) STORED
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    id uuid NOT NULL,
    source_id uuid NOT NULL,
    source_path text NOT NULL,
    filename character varying(500) NOT NULL,
    file_type character varying(50) NOT NULL,
    file_hash character varying(64) NOT NULL,
    file_size integer DEFAULT 0 NOT NULL,
    ingestion_status public.ingestion_status DEFAULT 'pending'::public.ingestion_status NOT NULL,
    ingestion_error text,
    chunk_count integer DEFAULT 0 NOT NULL,
    ingested_at timestamp with time zone,
    metadata jsonb,
    display_name character varying(500),
    department_id uuid,
    redaction_status character varying(20) DEFAULT 'none'::character varying NOT NULL,
    derivative_path character varying(1000),
    original_locked boolean DEFAULT false NOT NULL,
    connector_type character varying(20),
    updated_at timestamp with time zone,
    CONSTRAINT chk_source_path_length CHECK (((source_path IS NULL) OR (length(source_path) <= 2048)))
);


--
-- Name: exemption_flags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exemption_flags (
    id uuid NOT NULL,
    chunk_id uuid NOT NULL,
    rule_id uuid,
    request_id uuid NOT NULL,
    category character varying(100) NOT NULL,
    matched_text text,
    confidence double precision DEFAULT '1'::double precision NOT NULL,
    status public.flag_status DEFAULT 'flagged'::public.flag_status NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_reason text,
    created_at timestamp with time zone DEFAULT now(),
    review_note text,
    detection_tier integer,
    detection_method character varying(50),
    auto_detected boolean DEFAULT false NOT NULL
);


--
-- Name: exemption_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exemption_rules (
    id uuid NOT NULL,
    state_code character varying(2) NOT NULL,
    category character varying(100) NOT NULL,
    rule_type public.rule_type NOT NULL,
    rule_definition text NOT NULL,
    description text,
    enabled boolean DEFAULT true NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    version integer DEFAULT 1 NOT NULL
);


--
-- Name: fee_line_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fee_line_items (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    fee_schedule_id uuid,
    description character varying(500) NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    total numeric(10,2) NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: fee_schedules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fee_schedules (
    id uuid NOT NULL,
    jurisdiction character varying(100) NOT NULL,
    fee_type character varying(50) NOT NULL,
    amount numeric(10,2) NOT NULL,
    description character varying(500),
    effective_date date NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: fee_waivers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fee_waivers (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    waiver_type character varying(50) NOT NULL,
    reason character varying(2000) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    requested_by uuid,
    reviewed_by uuid,
    review_notes character varying(2000),
    created_at timestamp with time zone DEFAULT now(),
    reviewed_at timestamp with time zone
);


--
-- Name: model_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_registry (
    id integer NOT NULL,
    model_name character varying(255) NOT NULL,
    model_version character varying(100),
    parameter_count character varying(50),
    license character varying(100),
    model_card_url text,
    is_active boolean DEFAULT false NOT NULL,
    added_at timestamp with time zone DEFAULT now(),
    context_window_size integer,
    supports_ner boolean DEFAULT false NOT NULL,
    supports_vision boolean DEFAULT false NOT NULL
);


--
-- Name: model_registry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.model_registry_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: model_registry_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.model_registry_id_seq OWNED BY public.model_registry.id;


--
-- Name: notification_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_log (
    id uuid NOT NULL,
    template_id uuid,
    recipient_email character varying(255) NOT NULL,
    request_id uuid,
    channel character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    sent_at timestamp with time zone,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    subject character varying(500),
    body text
);


--
-- Name: notification_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_templates (
    id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    channel character varying(20) NOT NULL,
    subject_template character varying(500) NOT NULL,
    body_template text NOT NULL,
    is_active boolean NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: prompt_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prompt_templates (
    id uuid NOT NULL,
    name character varying(200) NOT NULL,
    purpose character varying(50) NOT NULL,
    system_prompt text NOT NULL,
    user_prompt_template text NOT NULL,
    token_budget jsonb NOT NULL,
    model_id integer,
    version integer NOT NULL,
    is_active boolean NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: records_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.records_requests (
    id uuid NOT NULL,
    requester_name character varying(255) NOT NULL,
    requester_email character varying(320),
    date_received timestamp with time zone DEFAULT now(),
    statutory_deadline timestamp with time zone,
    description text NOT NULL,
    status public.request_status DEFAULT 'received'::public.request_status NOT NULL,
    assigned_to uuid,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    response_draft text,
    review_notes text,
    requester_phone character varying(50),
    requester_type character varying(20),
    scope_assessment character varying(20),
    department_id uuid,
    estimated_fee numeric(10,2),
    fee_status character varying(20),
    fee_waiver_requested boolean DEFAULT false NOT NULL,
    priority character varying(20) DEFAULT 'normal'::character varying NOT NULL,
    closed_at timestamp with time zone,
    closure_reason character varying(500)
);


--
-- Name: request_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.request_documents (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    document_id uuid NOT NULL,
    relevance_note text,
    exemption_flags jsonb,
    inclusion_status public.inclusion_status DEFAULT 'pending'::public.inclusion_status NOT NULL,
    attached_at timestamp with time zone DEFAULT now(),
    attached_by uuid NOT NULL
);


--
-- Name: request_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.request_messages (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    sender_type character varying(20) NOT NULL,
    sender_id uuid,
    message_text text NOT NULL,
    is_internal boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: request_timeline; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.request_timeline (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    actor_id uuid,
    actor_role character varying(50),
    description text NOT NULL,
    internal_note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: response_letters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.response_letters (
    id uuid NOT NULL,
    request_id uuid NOT NULL,
    template_id uuid,
    generated_content text NOT NULL,
    edited_content text,
    status character varying(20) NOT NULL,
    generated_by uuid,
    approved_by uuid,
    sent_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: search_queries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_queries (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    query_text text NOT NULL,
    filters jsonb,
    results_count integer DEFAULT 0 NOT NULL,
    synthesized_answer text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: search_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_results (
    id uuid NOT NULL,
    query_id uuid NOT NULL,
    chunk_id uuid NOT NULL,
    similarity_score double precision NOT NULL,
    rank integer NOT NULL,
    normalized_score integer
);


--
-- Name: search_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: service_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_accounts (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    api_key_hash character varying(255) NOT NULL,
    role public.user_role DEFAULT 'read_only'::public.user_role NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    is_active boolean DEFAULT true NOT NULL
);


--
-- Name: sync_failures; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_failures (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_id uuid NOT NULL,
    source_path text NOT NULL,
    error_message text,
    error_class character varying(200),
    http_status_code integer,
    retry_count integer DEFAULT 0 NOT NULL,
    status character varying(20) DEFAULT 'retrying'::character varying NOT NULL,
    first_failed_at timestamp with time zone DEFAULT now() NOT NULL,
    last_retried_at timestamp with time zone,
    resolved_at timestamp with time zone,
    dismissed_at timestamp with time zone,
    dismissed_by uuid
);


--
-- Name: sync_run_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sync_run_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_id uuid NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    status character varying(20),
    records_attempted integer DEFAULT 0,
    records_succeeded integer DEFAULT 0,
    records_failed integer DEFAULT 0,
    error_summary text
);


--
-- Name: system_catalog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_catalog (
    id integer NOT NULL,
    domain character varying(100) NOT NULL,
    function character varying(200) NOT NULL,
    vendor_name character varying(200) NOT NULL,
    vendor_version character varying(50),
    access_protocol character varying(50) NOT NULL,
    data_shape character varying(50) NOT NULL,
    common_record_types jsonb NOT NULL,
    redaction_tier integer NOT NULL,
    discovery_hints jsonb NOT NULL,
    connector_template_id integer,
    catalog_version character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: system_catalog_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_catalog_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_catalog_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_catalog_id_seq OWNED BY public.system_catalog.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(320) NOT NULL,
    hashed_password character varying(1024) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    is_superuser boolean DEFAULT false NOT NULL,
    is_verified boolean DEFAULT false NOT NULL,
    full_name character varying DEFAULT ''::character varying NOT NULL,
    role public.user_role DEFAULT 'staff'::public.user_role NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    last_login timestamp with time zone,
    department_id uuid
);


--
-- Name: _migration_015_report id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._migration_015_report ALTER COLUMN id SET DEFAULT nextval('public._migration_015_report_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: connector_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_templates ALTER COLUMN id SET DEFAULT nextval('public.connector_templates_id_seq'::regclass);


--
-- Name: model_registry id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_registry ALTER COLUMN id SET DEFAULT nextval('public.model_registry_id_seq'::regclass);


--
-- Name: system_catalog id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_catalog ALTER COLUMN id SET DEFAULT nextval('public.system_catalog_id_seq'::regclass);


--
-- Name: _migration_015_report _migration_015_report_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._migration_015_report
    ADD CONSTRAINT _migration_015_report_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: city_profile city_profile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.city_profile
    ADD CONSTRAINT city_profile_pkey PRIMARY KEY (id);


--
-- Name: connector_templates connector_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connector_templates
    ADD CONSTRAINT connector_templates_pkey PRIMARY KEY (id);


--
-- Name: data_sources data_sources_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_sources
    ADD CONSTRAINT data_sources_name_key UNIQUE (name);


--
-- Name: data_sources data_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_sources
    ADD CONSTRAINT data_sources_pkey PRIMARY KEY (id);


--
-- Name: departments departments_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_code_key UNIQUE (code);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: disclosure_templates disclosure_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disclosure_templates
    ADD CONSTRAINT disclosure_templates_pkey PRIMARY KEY (id);


--
-- Name: document_cache document_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_cache
    ADD CONSTRAINT document_cache_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: exemption_flags exemption_flags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_flags
    ADD CONSTRAINT exemption_flags_pkey PRIMARY KEY (id);


--
-- Name: exemption_rules exemption_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_rules
    ADD CONSTRAINT exemption_rules_pkey PRIMARY KEY (id);


--
-- Name: fee_line_items fee_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_line_items
    ADD CONSTRAINT fee_line_items_pkey PRIMARY KEY (id);


--
-- Name: fee_schedules fee_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_schedules
    ADD CONSTRAINT fee_schedules_pkey PRIMARY KEY (id);


--
-- Name: fee_waivers fee_waivers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_waivers
    ADD CONSTRAINT fee_waivers_pkey PRIMARY KEY (id);


--
-- Name: model_registry model_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_registry
    ADD CONSTRAINT model_registry_pkey PRIMARY KEY (id);


--
-- Name: notification_log notification_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_log
    ADD CONSTRAINT notification_log_pkey PRIMARY KEY (id);


--
-- Name: notification_templates notification_templates_event_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_event_type_key UNIQUE (event_type);


--
-- Name: notification_templates notification_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_pkey PRIMARY KEY (id);


--
-- Name: prompt_templates prompt_templates_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_name_key UNIQUE (name);


--
-- Name: prompt_templates prompt_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_pkey PRIMARY KEY (id);


--
-- Name: records_requests records_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.records_requests
    ADD CONSTRAINT records_requests_pkey PRIMARY KEY (id);


--
-- Name: request_documents request_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_documents
    ADD CONSTRAINT request_documents_pkey PRIMARY KEY (id);


--
-- Name: request_messages request_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_messages
    ADD CONSTRAINT request_messages_pkey PRIMARY KEY (id);


--
-- Name: request_timeline request_timeline_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_timeline
    ADD CONSTRAINT request_timeline_pkey PRIMARY KEY (id);


--
-- Name: response_letters response_letters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.response_letters
    ADD CONSTRAINT response_letters_pkey PRIMARY KEY (id);


--
-- Name: search_queries search_queries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_queries
    ADD CONSTRAINT search_queries_pkey PRIMARY KEY (id);


--
-- Name: search_results search_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_pkey PRIMARY KEY (id);


--
-- Name: search_sessions search_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_pkey PRIMARY KEY (id);


--
-- Name: service_accounts service_accounts_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_name_key UNIQUE (name);


--
-- Name: service_accounts service_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_pkey PRIMARY KEY (id);


--
-- Name: sync_failures sync_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_failures
    ADD CONSTRAINT sync_failures_pkey PRIMARY KEY (id);


--
-- Name: sync_run_log sync_run_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_run_log
    ADD CONSTRAINT sync_run_log_pkey PRIMARY KEY (id);


--
-- Name: system_catalog system_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_catalog
    ADD CONSTRAINT system_catalog_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_log_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_action ON public.audit_log USING btree (action);


--
-- Name: ix_audit_log_entry_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_entry_hash ON public.audit_log USING btree (entry_hash);


--
-- Name: ix_audit_log_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_resource_type ON public.audit_log USING btree (resource_type);


--
-- Name: ix_audit_log_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_timestamp ON public.audit_log USING btree ("timestamp");


--
-- Name: ix_audit_log_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_user_id ON public.audit_log USING btree (user_id);


--
-- Name: ix_audit_log_user_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_log_user_timestamp ON public.audit_log USING btree (user_id, "timestamp");


--
-- Name: ix_chunks_doc_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunks_doc_index ON public.document_chunks USING btree (document_id, chunk_index);


--
-- Name: ix_chunks_embedding_hnsw; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunks_embedding_hnsw ON public.document_chunks USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: ix_chunks_tsvector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chunks_tsvector ON public.document_chunks USING gin (content_tsvector);


--
-- Name: ix_document_cache_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_cache_document_id ON public.document_cache USING btree (document_id);


--
-- Name: ix_document_cache_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_cache_request_id ON public.document_cache USING btree (request_id);


--
-- Name: ix_document_chunks_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_chunks_document_id ON public.document_chunks USING btree (document_id);


--
-- Name: ix_documents_file_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_file_hash ON public.documents USING btree (file_hash);


--
-- Name: ix_documents_source_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_source_hash ON public.documents USING btree (source_id, file_hash);


--
-- Name: ix_documents_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_source_id ON public.documents USING btree (source_id);


--
-- Name: ix_exemption_flags_chunk; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_flags_chunk ON public.exemption_flags USING btree (chunk_id);


--
-- Name: ix_exemption_flags_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_flags_request ON public.exemption_flags USING btree (request_id);


--
-- Name: ix_exemption_flags_rule; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_flags_rule ON public.exemption_flags USING btree (rule_id);


--
-- Name: ix_exemption_flags_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_flags_status ON public.exemption_flags USING btree (status);


--
-- Name: ix_exemption_rules_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_rules_category ON public.exemption_rules USING btree (category);


--
-- Name: ix_exemption_rules_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exemption_rules_state ON public.exemption_rules USING btree (state_code);


--
-- Name: ix_fee_waivers_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fee_waivers_request_id ON public.fee_waivers USING btree (request_id);


--
-- Name: ix_request_documents_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_request_documents_document_id ON public.request_documents USING btree (document_id);


--
-- Name: ix_request_documents_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_request_documents_request_id ON public.request_documents USING btree (request_id);


--
-- Name: ix_request_messages_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_request_messages_request_id ON public.request_messages USING btree (request_id);


--
-- Name: ix_request_timeline_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_request_timeline_request_id ON public.request_timeline USING btree (request_id);


--
-- Name: ix_requests_assigned_to; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_assigned_to ON public.records_requests USING btree (assigned_to);


--
-- Name: ix_requests_deadline; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_deadline ON public.records_requests USING btree (statutory_deadline);


--
-- Name: ix_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_requests_status ON public.records_requests USING btree (status);


--
-- Name: ix_response_letters_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_response_letters_request_id ON public.response_letters USING btree (request_id);


--
-- Name: ix_search_queries_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_queries_session_id ON public.search_queries USING btree (session_id);


--
-- Name: ix_search_results_chunk_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_results_chunk_id ON public.search_results USING btree (chunk_id);


--
-- Name: ix_search_results_query_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_results_query_id ON public.search_results USING btree (query_id);


--
-- Name: ix_search_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_sessions_user_id ON public.search_sessions USING btree (user_id);


--
-- Name: ix_sync_failures_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_failures_created ON public.sync_failures USING btree (first_failed_at);


--
-- Name: ix_sync_failures_source_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_failures_source_status ON public.sync_failures USING btree (source_id, status);


--
-- Name: ix_sync_run_log_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sync_run_log_source ON public.sync_run_log USING btree (source_id, started_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: uq_documents_binary_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_documents_binary_hash ON public.documents USING btree (source_id, file_hash) WHERE ((connector_type)::text <> ALL ((ARRAY['rest_api'::character varying, 'odbc'::character varying])::text[]));


--
-- Name: uq_documents_structured_path; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_documents_structured_path ON public.documents USING btree (source_id, source_path) WHERE ((connector_type)::text = ANY ((ARRAY['rest_api'::character varying, 'odbc'::character varying])::text[]));


--
-- Name: city_profile city_profile_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.city_profile
    ADD CONSTRAINT city_profile_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: data_sources data_sources_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_sources
    ADD CONSTRAINT data_sources_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: disclosure_templates disclosure_templates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disclosure_templates
    ADD CONSTRAINT disclosure_templates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: document_cache document_cache_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_cache
    ADD CONSTRAINT document_cache_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_cache document_cache_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_cache
    ADD CONSTRAINT document_cache_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id);


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: documents documents_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.data_sources(id);


--
-- Name: exemption_flags exemption_flags_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_flags
    ADD CONSTRAINT exemption_flags_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id);


--
-- Name: exemption_flags exemption_flags_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_flags
    ADD CONSTRAINT exemption_flags_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id);


--
-- Name: exemption_flags exemption_flags_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_flags
    ADD CONSTRAINT exemption_flags_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id);


--
-- Name: exemption_flags exemption_flags_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_flags
    ADD CONSTRAINT exemption_flags_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.exemption_rules(id);


--
-- Name: exemption_rules exemption_rules_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exemption_rules
    ADD CONSTRAINT exemption_rules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: fee_line_items fee_line_items_fee_schedule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_line_items
    ADD CONSTRAINT fee_line_items_fee_schedule_id_fkey FOREIGN KEY (fee_schedule_id) REFERENCES public.fee_schedules(id) ON DELETE SET NULL;


--
-- Name: fee_line_items fee_line_items_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_line_items
    ADD CONSTRAINT fee_line_items_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE CASCADE;


--
-- Name: fee_schedules fee_schedules_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_schedules
    ADD CONSTRAINT fee_schedules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: fee_waivers fee_waivers_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_waivers
    ADD CONSTRAINT fee_waivers_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE CASCADE;


--
-- Name: fee_waivers fee_waivers_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_waivers
    ADD CONSTRAINT fee_waivers_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: fee_waivers fee_waivers_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fee_waivers
    ADD CONSTRAINT fee_waivers_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: users fk_users_department; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_department FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: notification_log notification_log_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_log
    ADD CONSTRAINT notification_log_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE SET NULL;


--
-- Name: notification_log notification_log_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_log
    ADD CONSTRAINT notification_log_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.notification_templates(id) ON DELETE SET NULL;


--
-- Name: notification_templates notification_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: prompt_templates prompt_templates_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: prompt_templates prompt_templates_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prompt_templates
    ADD CONSTRAINT prompt_templates_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_registry(id) ON DELETE SET NULL;


--
-- Name: records_requests records_requests_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.records_requests
    ADD CONSTRAINT records_requests_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.users(id);


--
-- Name: records_requests records_requests_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.records_requests
    ADD CONSTRAINT records_requests_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: request_documents request_documents_attached_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_documents
    ADD CONSTRAINT request_documents_attached_by_fkey FOREIGN KEY (attached_by) REFERENCES public.users(id);


--
-- Name: request_documents request_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_documents
    ADD CONSTRAINT request_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: request_documents request_documents_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_documents
    ADD CONSTRAINT request_documents_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id);


--
-- Name: request_messages request_messages_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_messages
    ADD CONSTRAINT request_messages_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE CASCADE;


--
-- Name: request_messages request_messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_messages
    ADD CONSTRAINT request_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: request_timeline request_timeline_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_timeline
    ADD CONSTRAINT request_timeline_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: request_timeline request_timeline_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.request_timeline
    ADD CONSTRAINT request_timeline_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE CASCADE;


--
-- Name: response_letters response_letters_approved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.response_letters
    ADD CONSTRAINT response_letters_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: response_letters response_letters_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.response_letters
    ADD CONSTRAINT response_letters_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: response_letters response_letters_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.response_letters
    ADD CONSTRAINT response_letters_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.records_requests(id) ON DELETE CASCADE;


--
-- Name: response_letters response_letters_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.response_letters
    ADD CONSTRAINT response_letters_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.disclosure_templates(id) ON DELETE SET NULL;


--
-- Name: search_queries search_queries_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_queries
    ADD CONSTRAINT search_queries_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.search_sessions(id);


--
-- Name: search_results search_results_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id);


--
-- Name: search_results search_results_query_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_query_id_fkey FOREIGN KEY (query_id) REFERENCES public.search_queries(id);


--
-- Name: search_sessions search_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: service_accounts service_accounts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: sync_failures sync_failures_dismissed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_failures
    ADD CONSTRAINT sync_failures_dismissed_by_fkey FOREIGN KEY (dismissed_by) REFERENCES public.users(id);


--
-- Name: sync_failures sync_failures_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_failures
    ADD CONSTRAINT sync_failures_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.data_sources(id) ON DELETE CASCADE;


--
-- Name: sync_run_log sync_run_log_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sync_run_log
    ADD CONSTRAINT sync_run_log_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.data_sources(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict TpzmFDtyaibtowKM0WiehKumAMSgl4LOw1DpKHsXzWC4AXlEOHxqI5DxqSE3rhR

