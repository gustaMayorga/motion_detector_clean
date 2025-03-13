SYSTEM_CONFIG = {
    'deployment_mode': 'hybrid',  # 'cloud', 'local', 'hybrid'
    'storage': {
        'event_retention': '30d',
        'storage_type': 'selective',  # 'full', 'selective', 'minimal'
    },
    'ml_settings': {
        'update_frequency': '7d',
        'min_confidence': 0.85
    },
    'communication': {
        'primary_channel': 'whatsapp',
        'backup_channels': ['push', 'email']
    }
} 