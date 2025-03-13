    def _draw_event(self, frame, event):
        """Dibujar evento detectado"""
        event_type = event['type']
        bbox = event['bbox']
        position = event.get('position', (0, 0))
        
        # Colores según tipo de evento
        colors = {
            'loitering': (0, 0, 255),      # Rojo
            'intrusion': (0, 0, 255),      # Rojo
            'tailgating': (255, 165, 0),   # Azul claro
            'abandoned_object': (0, 255, 255), # Amarillo
            'default': (255, 255, 255)     # Blanco
        }
        
        # Obtener color para este tipo de evento
        color = colors.get(event_type, colors['default'])
        
        # Dibujar rectángulo de alerta
        x1, y1, x2, y2 = bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        
        # Dibujar texto de alerta
        alert_text = event_type.upper()
        cv2.putText(frame, alert_text, (x1, y1 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                   
        # Dibujar líneas o marcadores específicos según el tipo de evento
        if event_type == 'tailgating':
            # Para tailgating, dibujar una línea entre líder y seguidor
            if 'leader_id' in event and 'follower_id' in event:
                leader_id = event['leader_id']
                follower_id = event['follower_id']
                
                if leader_id in self.tracked_objects and follower_id in self.tracked_objects:
                    leader = self.tracked_objects[leader_id]
                    follower = self.tracked_objects[follower_id]
                    
                    leader_pos = leader.path[-1]
                    follower_pos = follower.path[-1]
                    
                    cv2.line(frame, leader_pos, follower_pos, color, 2)
                    cv2.putText(frame, "TAILGATING", 
                              (int((leader_pos[0] + follower_pos[0])/2), 
                               int((leader_pos[1] + follower_pos[1])/2)),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                              
        elif event_type == 'loitering':
            # Para loitering, dibujar el área de permanencia
            radius = event.get('radius', 50)
            cv2.circle(frame, position, radius, color, 2)
            cv2.putText(frame, f"LOITERING ({event.get('duration', 0)/30:.1f}s)", 
                      (position[0], position[1] - 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                      
        elif event_type == 'intrusion':
            # Para intrusión, resaltar la zona violada
            zone_name = event.get('zone', '')
            if zone_name in self.config['zones']:
                zone_info = self.config['zones'][zone_name]
                polygon = zone_info['polygon']
                
                # Dibujar polígono con color de alerta
                points = np.array(polygon, np.int32)
                points = points.reshape((-1, 1, 2))
                cv2.polylines(frame, [points], True, color, 3)
                
                # Rellenar con transparencia
                overlay = frame.copy()
                cv2.fillPoly(overlay, [points], color)
                alpha = 0.3  # Transparencia
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
                
        elif event_type == 'abandoned_object':
            # Para objeto abandonado, dibujar un círculo y tiempo
            cv2.circle(frame, position, 30, color, 2)
            duration = event.get('duration', 0) / 30  # Convertir frames a segundos
            cv2.putText(frame, f"ABANDONED ({duration:.1f}s)", 
                      (position[0], position[1] - 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                      
        return frame
        
    def _point_in_polygon(self, point, polygon):
        """Comprobar si un punto está dentro de un polígono"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        return inside
        
    def _check_zones(self, obj):
        """Comprobar en qué zonas está un objeto"""
        zones = set()
        
        # Obtener posición actual (centro del objeto)
        if not obj.path:
            return zones
            
        point = obj.path[-1]
        
        # Comprobar cada zona
        for zone_name, zone_info in self.config['zones'].items():
            polygon = zone_info['polygon']
            if self._point_in_polygon(point, polygon):
                zones.add(zone_name)
                
        return zones
        
    def _register_object(self, centroid, bbox, class_info, confidence):
        """Registrar un nuevo objeto para seguimiento"""
        class_id, class_name = class_info
        object_id = self._generate_unique_id()
        
        # Generar color único basado en ID para visualización
        color_hash = sum(ord(c) for c in object_id) % 256
        color = (
            (color_hash * 71) % 256,  # B
            (color_hash * 237) % 256, # G
            (color_hash * 157) % 256  # R
        )
        
        # Crear objeto de seguimiento
        tracked_object = TrackedObject(
            object_id=object_id,
            class_id=class_id,
            class_name=class_name,
            positions=deque([(self.frame_id, bbox[0], bbox[1], bbox[2], bbox[3], confidence)],
                           maxlen=self.config['max_history']),
            last_seen=self.frame_id,
            color=color,
            first_seen=self.frame_id,
            path=[centroid],
            speed=0.0,
            direction=(0.0, 0.0),
            zones=set(),
            meta={}
        )
        
        # Comprobar zonas
        tracked_object.zones = self._check_zones(tracked_object)
        
        # Registrar objeto
        self.tracked_objects[object_id] = tracked_object
        
        return object_id
        
    def _update_object(self, object_id, centroid, bbox, confidence):
        """Actualizar información de un objeto rastreado"""
        obj = self.tracked_objects[object_id]
        
        # Actualizar posiciones y trayectoria
        obj.positions.append((self.frame_id, bbox[0], bbox[1], bbox[2], bbox[3], confidence))
        obj.path.append(centroid)
        
        # Actualizar timestamp de última visualización
        obj.last_seen = self.frame_id
        
        # Actualizar velocidad y dirección si hay suficientes posiciones
        if len(obj.path) >= 2:
            p1 = obj.path[-2]
            p2 = obj.path[-1]
            
            # Calcular velocidad (pixels/frame)
            distance = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
            obj.speed = distance
            
            # Calcular dirección (vector unitario)
            if distance > 0:
                obj.direction = ((p2[0] - p1[0]) / distance, (p2[1] - p1[1]) / distance)
                
        # Actualizar zonas
        obj.zones = self._check_zones(obj)
        
        # Reiniciar contador de desaparición
        self.disappeared[object_id] = 0
        
    def _deregister_object(self, object_id):
        """Eliminar un objeto del seguimiento"""
        del self.tracked_objects[object_id]
        del self.disappeared[object_id]
        
    def reset(self):
        """Reiniciar el estado del tracker"""
        self.tracked_objects.clear()
        self.disappeared.clear()
        self.alerts.clear()
        self.frame_id = 0
        
    def get_object_count(self, class_filter=None):
        """
        Obtener número de objetos rastreados, opcionalmente filtrados por clase
        
        Args:
            class_filter: Nombre de clase para filtrar o lista de clases
            
        Returns:
            Número de objetos que coinciden con el filtro
        """
        if class_filter is None:
            return len(self.tracked_objects)
            
        if isinstance(class_filter, str):
            class_filter = [class_filter]
            
        return sum(1 for obj in self.tracked_objects.values() 
                  if obj.class_name in class_filter)
                  
    def get_zone_counts(self):
        """
        Obtener conteo de objetos por zona
        
        Returns:
            Diccionario {zone_name: {class_name: count}}
        """
        counts = {zone: defaultdict(int) for zone in self.config['zones']}
        
        for obj in self.tracked_objects.values():
            for zone in obj.zones:
                if zone in counts:
                    counts[zone][obj.class_name] += 1
                    
        return counts
        
    def get_tracked_objects(self, class_filter=None, zone_filter=None):
        """
        Obtener objetos rastreados con filtros opcionales
        
        Args:
            class_filter: Filtrar por clase o lista de clases
            zone_filter: Filtrar por zona o lista de zonas
            
        Returns:
            Lista de objetos rastreados que coinciden con los filtros
        """
        result = list(self.tracked_objects.values())
        
        # Filtrar por clase
        if class_filter:
            if isinstance(class_filter, str):
                class_filter = [class_filter]
            result = [obj for obj in result if obj.class_name in class_filter]
            
        # Filtrar por zona
        if zone_filter:
            if isinstance(zone_filter, str):
                zone_filter = [zone_filter]
            result = [obj for obj in result if any(zone in obj.zones for zone in zone_filter)]
            
        return result
        
    def get_events_history(self, limit=100, event_type=None):
        """
        Obtener historial de eventos/alertas
        
        Args:
            limit: Número máximo de eventos a retornar
            event_type: Filtrar por tipo de evento
            
        Returns:
            Lista de eventos ordenados por tiempo (más reciente primero)
        """
        if event_type:
            filtered_events = [event for event in self.alerts if event['type'] == event_type]
        else:
            filtered_events = self.alerts
            
        # Ordenar por frame_id (descendente)
        sorted_events = sorted(filtered_events, key=lambda e: e['frame_id'], reverse=True)
        
        return sorted_events[:limit]
        
    def set_zone_definition(self, zone_name, polygon, color=None):
        """
        Definir o actualizar una zona
        
        Args:
            zone_name: Nombre de la zona
            polygon: Lista de puntos [(x1,y1), (x2,y2), ...]
            color: Tupla BGR (opcional)
        """
        if zone_name not in self.config['zones']:
            # Crear nueva zona
            self.config['zones'][zone_name] = {
                'polygon': polygon,
                'color': color or (0, 255, 0)  # Verde por defecto
            }
        else:
            # Actualizar zona existente
            self.config['zones'][zone_name]['polygon'] = polygon
            if color:
                self.config['zones'][zone_name]['color'] = color
                
        self.logger.info(f"Zona '{zone_name}' configurada con {len(polygon)} puntos")
        
    def delete_zone(self, zone_name):
        """Eliminar una zona definida"""
        if zone_name in self.config['zones']:
            del self.config['zones'][zone_name]
            self.logger.info(f"Zona '{zone_name}' eliminada")
            return True
        return False
        
    def export_config(self):
        """Exportar configuración actual"""
        return self.config
        
    def import_config(self, config):
        """Importar configuración"""
        self.config = config
        self.logger.info("Configuración importada")
        
        # Reiniciar tracker para aplicar nueva configuración
        self._init_tracker() 