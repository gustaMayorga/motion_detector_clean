import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Text, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

# Mixin para timestamps comunes
class TimestampMixin:
    """Mixin para añadir timestamps automáticos a los modelos"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# Tabla de asociación para la relación many-to-many entre roles y permisos
role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id'), primary_key=True)
)

class User(Base, TimestampMixin):
    """Modelo para usuarios del sistema"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relaciones
    role = relationship("Role", back_populates="users")
    sessions = relationship("Session", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.username}>"

class Role(Base, TimestampMixin):
    """Modelo para roles de usuario"""
    __tablename__ = 'roles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    
    # Relaciones
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    
    def __repr__(self):
        return f"<Role {self.name}>"

class Permission(Base, TimestampMixin):
    """Modelo para permisos"""
    __tablename__ = 'permissions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    
    # Relaciones
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission {self.name}>"

class Session(Base, TimestampMixin):
    """Modelo para sesiones de usuario"""
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    expires_at = Column(DateTime, nullable=False)
    
    # Relaciones
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session {self.id} - User {self.user_id}>"

class Camera(Base, TimestampMixin):
    """Modelo para cámaras del sistema"""
    __tablename__ = 'cameras'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    vendor = Column(String(50), nullable=False)
    ip = Column(String(50), nullable=False)
    username = Column(String(50))
    password = Column(String(255))
    rtsp_url = Column(String(255))
    fps = Column(Integer, default=10)
    resolution = Column(String(20))
    config = Column(JSON, default={})
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relaciones
    zones = relationship("Zone", back_populates="camera")
    recordings = relationship("Recording", back_populates="camera")
    
    def __repr__(self):
        return f"<Camera {self.name}>"

class Zone(Base, TimestampMixin):
    """Modelo para zonas de detección"""
    __tablename__ = 'zones'
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False)
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # intrusion, loitering, line, etc.
    points = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...]
    color = Column(String(20))
    is_active = Column(Boolean, default=True)
    
    # Relaciones
    camera = relationship("Camera", back_populates="zones")
    alerts = relationship("Alert", back_populates="zone")
    
    __table_args__ = {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    
    def __repr__(self):
        return f"<Zone {self.name} - Camera {self.camera_id}>"

class Recording(Base, TimestampMixin):
    """Modelo para grabaciones de video"""
    __tablename__ = 'recordings'
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration = Column(Integer)  # en segundos
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer)  # en bytes
    has_alerts = Column(Boolean, default=False, nullable=False)
    
    # Relaciones
    camera = relationship("Camera", back_populates="recordings")
    alerts = relationship("Alert", back_populates="recording")
    detected_objects = relationship("DetectedObject", back_populates="recording")
    
    def __repr__(self):
        return f"<Recording {self.id} - Camera {self.camera_id}>"

class Alert(Base, TimestampMixin):
    """Modelo para alertas"""
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False)
    recording_id = Column(Integer, ForeignKey('recordings.id'))
    event_type = Column(String(50), nullable=False)  # intrusion, loitering, etc.
    priority = Column(String(20), nullable=False)  # high, medium, low
    timestamp = Column(DateTime, nullable=False)
    frame_number = Column(Integer)
    bbox = Column(JSON)  # [x1, y1, x2, y2]
    screenshot_path = Column(Text)
    zone_id = Column(Integer, ForeignKey('zones.id'))
    object_ids = Column(JSON)  # [id1, id2, ...]
    alert_metadata = Column(JSON)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_by = Column(Integer, ForeignKey('users.id'))
    acknowledged_at = Column(DateTime)
    notes = Column(Text)
    
    # Relaciones
    camera = relationship("Camera")
    recording = relationship("Recording", back_populates="alerts")
    zone = relationship("Zone", back_populates="alerts")
    acknowledger = relationship("User")
    
    def __repr__(self):
        return f"<Alert {self.id} - Type {self.event_type}>"

class DetectedObject(Base, TimestampMixin):
    """Modelo para objetos detectados"""
    __tablename__ = 'detected_objects'
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False)
    recording_id = Column(Integer, ForeignKey('recordings.id'))
    object_id = Column(String(50), nullable=False)
    class_id = Column(Integer, nullable=False)
    class_name = Column(String(50), nullable=False)
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    path = Column(JSON)  # [[frame_num, x, y], ...]
    confidence = Column(Float)
    
    # Relaciones
    camera = relationship("Camera")
    recording = relationship("Recording", back_populates="detected_objects")
    
    def __repr__(self):
        return f"<DetectedObject {self.id} - Class {self.class_name}>"

class Statistic(Base, TimestampMixin):
    """Modelo para estadísticas"""
    __tablename__ = 'statistics'
    
    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    hour = Column(Integer, nullable=False)  # 0-23
    people_count = Column(Integer, default=0, nullable=False)
    vehicle_count = Column(Integer, default=0, nullable=False)
    alert_count = Column(Integer, default=0, nullable=False)
    zone_counts = Column(JSON)  # {"zone_id": {"class_id": count}}
    
    # Relaciones
    camera = relationship("Camera")
    
    def __repr__(self):
        return f"<Statistic {self.id} - Camera {self.camera_id} - Date {self.date}>"

class SystemLog(Base, TimestampMixin):
    """Modelo para logs del sistema"""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    log_level = Column(String(20), nullable=False)
    component = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    ip_address = Column(String(45))
    
    # Relaciones
    user = relationship("User")
    
    def __repr__(self):
        return f"<SystemLog {self.id} - Level {self.log_level}>"

class SystemConfig(Base, TimestampMixin):
    """Modelo para configuración del sistema"""
    __tablename__ = 'system_config'
    
    id = Column(Integer, primary_key=True)
    section = Column(String(50), nullable=False)
    key = Column(String(50), nullable=False)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_by = Column(Integer, ForeignKey('users.id'))
    
    # Relaciones
    user = relationship("User")
    
    # Restricción única para sección+clave
    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )
    
    def __repr__(self):
        return f"<SystemConfig {self.section}.{self.key}>"

class Notification(Base, TimestampMixin):
    """Modelo para notificaciones de usuario"""
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime)
    
    # Relaciones
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification {self.id} - User {self.user_id}>" 
