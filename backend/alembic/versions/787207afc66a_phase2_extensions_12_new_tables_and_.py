"""phase2 extensions: 12 new tables and column additions

Revision ID: 787207afc66a
Revises: 006
Create Date: 2026-04-12 14:28:53.902505
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import fastapi_users_db_sqlalchemy.generics

# revision identifiers
revision: str = '787207afc66a'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === 12 New Tables ===

    op.create_table('connector_templates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vendor_name', sa.String(length=200), nullable=False),
    sa.Column('protocol', sa.String(length=50), nullable=False),
    sa.Column('auth_method', sa.String(length=50), nullable=False),
    sa.Column('config_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('default_sync_schedule', sa.String(length=50), nullable=True),
    sa.Column('default_rate_limit', sa.Integer(), nullable=True),
    sa.Column('redaction_tier', sa.Integer(), nullable=False),
    sa.Column('setup_instructions', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('catalog_version', sa.String(length=20), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('departments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('contact_email', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )

    op.create_table('system_catalog',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('domain', sa.String(length=100), nullable=False),
    sa.Column('function', sa.String(length=200), nullable=False),
    sa.Column('vendor_name', sa.String(length=200), nullable=False),
    sa.Column('vendor_version', sa.String(length=50), nullable=True),
    sa.Column('access_protocol', sa.String(length=50), nullable=False),
    sa.Column('data_shape', sa.String(length=50), nullable=False),
    sa.Column('common_record_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('redaction_tier', sa.Integer(), nullable=False),
    sa.Column('discovery_hints', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('connector_template_id', sa.Integer(), nullable=True),
    sa.Column('catalog_version', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('city_profile',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('city_name', sa.String(length=200), nullable=False),
    sa.Column('state', sa.String(length=2), nullable=False),
    sa.Column('county', sa.String(length=200), nullable=True),
    sa.Column('population_band', sa.String(length=50), nullable=True),
    sa.Column('email_platform', sa.String(length=50), nullable=True),
    sa.Column('has_dedicated_it', sa.Boolean(), nullable=True),
    sa.Column('monthly_request_volume', sa.String(length=20), nullable=True),
    sa.Column('onboarding_status', sa.String(length=20), nullable=False),
    sa.Column('profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('gap_map', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('fee_schedules',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('jurisdiction', sa.String(length=100), nullable=False),
    sa.Column('fee_type', sa.String(length=50), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('created_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('notification_templates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('subject_template', sa.String(length=500), nullable=False),
    sa.Column('body_template', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_type')
    )

    op.create_table('prompt_templates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('purpose', sa.String(length=50), nullable=False),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('user_prompt_template', sa.Text(), nullable=False),
    sa.Column('token_budget', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('model_id', sa.Integer(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['model_id'], ['model_registry.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )

    op.create_table('fee_line_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=False),
    sa.Column('fee_schedule_id', sa.Uuid(), nullable=True),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['fee_schedule_id'], ['fee_schedules.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['request_id'], ['records_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('notification_log',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('template_id', sa.Uuid(), nullable=True),
    sa.Column('recipient_email', sa.String(length=255), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=True),
    sa.Column('channel', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['records_requests.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['template_id'], ['notification_templates.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('request_messages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=False),
    sa.Column('sender_type', sa.String(length=20), nullable=False),
    sa.Column('sender_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('message_text', sa.Text(), nullable=False),
    sa.Column('is_internal', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['records_requests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_request_messages_request_id'), 'request_messages', ['request_id'], unique=False)

    op.create_table('request_timeline',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('actor_id', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('actor_role', sa.String(length=50), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('internal_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['request_id'], ['records_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_request_timeline_request_id'), 'request_timeline', ['request_id'], unique=False)

    op.create_table('response_letters',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.UUID(), nullable=False),
    sa.Column('template_id', sa.UUID(), nullable=True),
    sa.Column('generated_content', sa.Text(), nullable=False),
    sa.Column('edited_content', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('generated_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('approved_by', fastapi_users_db_sqlalchemy.generics.GUID(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['request_id'], ['records_requests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['template_id'], ['disclosure_templates.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_response_letters_request_id'), 'response_letters', ['request_id'], unique=False)

    # === Add new columns to existing tables ===

    # data_sources
    op.add_column('data_sources', sa.Column('discovered_source_id', sa.Uuid(), nullable=True))
    op.add_column('data_sources', sa.Column('connector_template_id', sa.Integer(), nullable=True))
    op.add_column('data_sources', sa.Column('sync_schedule', sa.String(50), nullable=True))
    op.add_column('data_sources', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('data_sources', sa.Column('last_sync_status', sa.String(20), nullable=True))
    op.add_column('data_sources', sa.Column('health_status', sa.String(20), nullable=True))
    op.add_column('data_sources', sa.Column('schema_hash', sa.String(64), nullable=True))

    # documents
    op.add_column('documents', sa.Column('display_name', sa.String(500), nullable=True))
    op.add_column('documents', sa.Column('department_id', sa.Uuid(), nullable=True))
    op.add_column('documents', sa.Column('redaction_status', sa.String(20), server_default='none', nullable=False))
    op.add_column('documents', sa.Column('derivative_path', sa.String(1000), nullable=True))
    op.add_column('documents', sa.Column('original_locked', sa.Boolean(), server_default='false', nullable=False))

    # records_requests
    op.add_column('records_requests', sa.Column('requester_phone', sa.String(50), nullable=True))
    op.add_column('records_requests', sa.Column('requester_type', sa.String(20), nullable=True))
    op.add_column('records_requests', sa.Column('scope_assessment', sa.String(20), nullable=True))
    op.add_column('records_requests', sa.Column('department_id', sa.Uuid(), nullable=True))
    op.add_column('records_requests', sa.Column('estimated_fee', sa.Numeric(10, 2), nullable=True))
    op.add_column('records_requests', sa.Column('fee_status', sa.String(20), nullable=True))
    op.add_column('records_requests', sa.Column('fee_waiver_requested', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('records_requests', sa.Column('priority', sa.String(20), server_default='normal', nullable=False))
    op.add_column('records_requests', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('records_requests', sa.Column('closure_reason', sa.String(500), nullable=True))

    # search_results
    op.add_column('search_results', sa.Column('normalized_score', sa.Integer(), nullable=True))

    # exemption_flags
    op.add_column('exemption_flags', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column('exemption_flags', sa.Column('detection_tier', sa.Integer(), nullable=True))
    op.add_column('exemption_flags', sa.Column('detection_method', sa.String(50), nullable=True))
    op.add_column('exemption_flags', sa.Column('auto_detected', sa.Boolean(), server_default='false', nullable=False))

    # model_registry
    op.add_column('model_registry', sa.Column('context_window_size', sa.Integer(), nullable=True))
    op.add_column('model_registry', sa.Column('supports_ner', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('model_registry', sa.Column('supports_vision', sa.Boolean(), server_default='false', nullable=False))

    # users — add department_id
    op.add_column('users', sa.Column('department_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_users_department', 'users', 'departments', ['department_id'], ['id'])


def downgrade() -> None:
    # === Drop new columns from existing tables ===

    # users
    op.drop_constraint('fk_users_department', 'users', type_='foreignkey')
    op.drop_column('users', 'department_id')

    # model_registry
    op.drop_column('model_registry', 'supports_vision')
    op.drop_column('model_registry', 'supports_ner')
    op.drop_column('model_registry', 'context_window_size')

    # exemption_flags
    op.drop_column('exemption_flags', 'auto_detected')
    op.drop_column('exemption_flags', 'detection_method')
    op.drop_column('exemption_flags', 'detection_tier')
    op.drop_column('exemption_flags', 'review_note')

    # search_results
    op.drop_column('search_results', 'normalized_score')

    # records_requests
    op.drop_column('records_requests', 'closure_reason')
    op.drop_column('records_requests', 'closed_at')
    op.drop_column('records_requests', 'priority')
    op.drop_column('records_requests', 'fee_waiver_requested')
    op.drop_column('records_requests', 'fee_status')
    op.drop_column('records_requests', 'estimated_fee')
    op.drop_column('records_requests', 'department_id')
    op.drop_column('records_requests', 'scope_assessment')
    op.drop_column('records_requests', 'requester_type')
    op.drop_column('records_requests', 'requester_phone')

    # documents
    op.drop_column('documents', 'original_locked')
    op.drop_column('documents', 'derivative_path')
    op.drop_column('documents', 'redaction_status')
    op.drop_column('documents', 'department_id')
    op.drop_column('documents', 'display_name')

    # data_sources
    op.drop_column('data_sources', 'schema_hash')
    op.drop_column('data_sources', 'health_status')
    op.drop_column('data_sources', 'last_sync_status')
    op.drop_column('data_sources', 'last_sync_at')
    op.drop_column('data_sources', 'sync_schedule')
    op.drop_column('data_sources', 'connector_template_id')
    op.drop_column('data_sources', 'discovered_source_id')

    # === Drop new tables ===
    op.drop_index(op.f('ix_response_letters_request_id'), table_name='response_letters')
    op.drop_table('response_letters')
    op.drop_index(op.f('ix_request_timeline_request_id'), table_name='request_timeline')
    op.drop_table('request_timeline')
    op.drop_index(op.f('ix_request_messages_request_id'), table_name='request_messages')
    op.drop_table('request_messages')
    op.drop_table('notification_log')
    op.drop_table('fee_line_items')
    op.drop_table('prompt_templates')
    op.drop_table('notification_templates')
    op.drop_table('fee_schedules')
    op.drop_table('city_profile')
    op.drop_table('system_catalog')
    op.drop_table('departments')
    op.drop_table('connector_templates')
