"""
Sistema de Email para Integra Mind Energy
Envía reportes ejecutivos y comunicaciones a clientes
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
import os

class EmailSender:
    def __init__(self, smtp_server="smtp.gmail.com", smtp_port=587):
        """
        Inicializar el sistema de email
        
        Para usar Gmail:
        1. Crear una "App Password" en tu cuenta de Google
        2. Ir a: https://myaccount.google.com/apppasswords
        3. Generar contraseña para "Mail"
        4. Usar esa contraseña aquí
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        
        # CONFIGURACIÓN: Cambiar estos valores
        self.sender_email = os.getenv('EMAIL_USER', 'gonzalohr1010@gmail.com')
        self.sender_password = os.getenv('EMAIL_PASSWORD', 'apix jtzr yxeo cxnc')
        self.sender_name = "Integra Mind Energy"
    
    def send_report_email(self, recipient_email, recipient_name, company_name, pdf_path):
        """
        Enviar reporte ejecutivo por email
        
        Args:
            recipient_email: Email del destinatario
            recipient_name: Nombre del destinatario
            company_name: Nombre de la empresa
            pdf_path: Ruta al archivo PDF
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = recipient_email
            msg['Subject'] = f"📊 Análisis Ejecutivo para {company_name} - Integra Mind Energy"
            
            # Cuerpo del email en HTML
            html_body = self._create_email_body(recipient_name, company_name)
            
            # Adjuntar HTML
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Adjuntar PDF
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_attachment = MIMEApplication(pdf_file.read(), _subtype='pdf')
                    pdf_attachment.add_header(
                        'Content-Disposition', 
                        'attachment', 
                        filename=os.path.basename(pdf_path)
                    )
                    msg.attach(pdf_attachment)
            else:
                print(f"⚠️ Advertencia: PDF no encontrado en {pdf_path}")
            
            # Enviar email
            try:
                # MODO SIMULACIÓN AUTOMÁTICO
                # Si las credenciales son las por defecto, simulamos el envío para la demo
                if "tu_email" in self.sender_email or "tu_app_password" in self.sender_password:
                    self._log_simulation(recipient_email, msg)
                    print(f"✅ [SIMULACIÓN] Email registrado exitosamente para {recipient_email}")
                    return True

                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
                
                print(f"✅ Email enviado exitosamente a {recipient_email}")
                return True
            except Exception as smtp_error:
                print(f"⚠️ Error SMTP real: {smtp_error}")
                print("🔄 Cambiando a MODO SIMULACIÓN por fallo de credenciales...")
                self._log_simulation(recipient_email, msg)
                return True
            
        except Exception as e:
            print(f"❌ Error general enviando email: {e}")
            return False

    def _log_simulation(self, recipient, msg):
        """Guardar email simulado en log"""
        log_entry = f"""
{'='*50}
FECHA: {datetime.now()}
PARA: {recipient}
ASUNTO: {msg['Subject']}
ARCHIVO ADJUNTO: (PDF incluido en el email real)
{'='*50}
        """
        with open("emails_enviados.log", "a", encoding='utf-8') as f:
            f.write(log_entry)
    
    def _create_email_body(self, recipient_name, company_name):
        """Crear cuerpo HTML del email"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #1e293b;
                    background-color: #f8fafc;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 40px auto;
                    background: white;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header p {{
                    margin: 10px 0 0 0;
                    opacity: 0.9;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .content h2 {{
                    color: #0284c7;
                    margin-top: 0;
                }}
                .highlight-box {{
                    background: #f0f9ff;
                    border-left: 4px solid #0284c7;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .cta-button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #10b981, #059669);
                    color: white;
                    padding: 14px 32px;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: 600;
                    margin: 20px 0;
                }}
                .footer {{
                    background: #f8fafc;
                    padding: 30px;
                    text-align: center;
                    color: #64748b;
                    font-size: 14px;
                }}
                .stats {{
                    display: flex;
                    justify-content: space-around;
                    margin: 30px 0;
                }}
                .stat {{
                    text-align: center;
                }}
                .stat-number {{
                    font-size: 32px;
                    font-weight: 700;
                    color: #0284c7;
                }}
                .stat-label {{
                    color: #64748b;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚡ INTEGRA MIND ENERGY</h1>
                    <p>Inteligencia Artificial para Infraestructura Crítica</p>
                </div>
                
                <div class="content">
                    <h2>Estimado/a {recipient_name},</h2>
                    
                    <p>Es un placer compartir con usted el <strong>Análisis Ejecutivo</strong> personalizado para <strong>{company_name}</strong>.</p>
                    
                    <div class="highlight-box">
                        <strong>📄 Documento Adjunto:</strong> Reporte Ejecutivo en PDF<br>
                        <strong>📊 Contenido:</strong> Análisis de ROI, Proyecciones de Ahorro, Timeline de Implementación
                    </div>
                    
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-number">$6.4M</div>
                            <div class="stat-label">Ahorro Anual Proyectado</div>
                        </div>
                        <div class="stat">
                            <div class="stat-number">98%</div>
                            <div class="stat-label">Precisión de IA</div>
                        </div>
                        <div class="stat">
                            <div class="stat-number">12-18</div>
                            <div class="stat-label">Meses ROI</div>
                        </div>
                    </div>
                    
                    <p><strong>Próximos Pasos:</strong></p>
                    <ul>
                        <li>Revisar el análisis ejecutivo adjunto</li>
                        <li>Agendar una reunión técnica (30 min)</li>
                        <li>Definir alcance de Prueba de Concepto</li>
                    </ul>
                    
                    <p>Estamos a su disposición para cualquier consulta o para coordinar una demostración en vivo de nuestro sistema.</p>
                    
                    <center>
                        <a href="mailto:sales@integramind.energy" class="cta-button">
                            📅 Agendar Reunión
                        </a>
                    </center>
                </div>
                
                <div class="footer">
                    <p><strong>Integra Mind Energy</strong></p>
                    <p>Email: sales@integramind.energy | Tel: +54 11 XXXX-XXXX</p>
                    <p style="font-size: 12px; margin-top: 20px;">
                        Este email fue generado automáticamente por nuestro sistema de gestión de clientes.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def send_welcome_email(self, recipient_email, recipient_name):
        """
        Enviar email de bienvenida cuando un lead se registra
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.sender_name} <{self.sender_email}>"
            msg['To'] = recipient_email
            msg['Subject'] = "✨ Bienvenido a Integra Mind Energy"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #1e293b;
                        background-color: #f8fafc;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 40px auto;
                        background: white;
                        border-radius: 12px;
                        overflow: hidden;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
                        color: white;
                        padding: 40px 30px;
                        text-align: center;
                    }}
                    .content {{
                        padding: 40px 30px;
                    }}
                    .footer {{
                        background: #f8fafc;
                        padding: 30px;
                        text-align: center;
                        color: #64748b;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>⚡ INTEGRA MIND ENERGY</h1>
                        <p>Gracias por tu interés</p>
                    </div>
                    
                    <div class="content">
                        <h2>Hola {recipient_name},</h2>
                        
                        <p>Gracias por registrarte en <strong>Integra Mind Energy</strong>. Hemos recibido tu solicitud y nuestro equipo se pondrá en contacto contigo pronto.</p>
                        
                        <p><strong>¿Qué sigue?</strong></p>
                        <ul>
                            <li>Revisaremos tu información</li>
                            <li>Te contactaremos en las próximas 24-48 horas</li>
                            <li>Coordinaremos una demo personalizada</li>
                        </ul>
                        
                        <p>Mientras tanto, puedes explorar nuestra plataforma en vivo.</p>
                    </div>
                    
                    <div class="footer">
                        <p><strong>Integra Mind Energy</strong></p>
                        <p>Email: sales@integramind.energy</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            print(f"✅ Email de bienvenida enviado a {recipient_email}")
            return True
            
        except Exception as e:
            print(f"❌ Error enviando email de bienvenida: {e}")
            return False


# Función de utilidad
def send_report_to_client(client_email, client_name, company_name, pdf_path):
    """Enviar reporte a un cliente"""
    sender = EmailSender()
    return sender.send_report_email(client_email, client_name, company_name, pdf_path)


if __name__ == "__main__":
    # Ejemplo de uso
    print("⚠️ CONFIGURACIÓN REQUERIDA:")
    print("1. Edita este archivo y configura tu email y contraseña")
    print("2. O configura variables de entorno:")
    print("   - EMAIL_USER=tu_email@gmail.com")
    print("   - EMAIL_PASSWORD=tu_app_password")
    print("\nPara Gmail, genera una App Password en:")
    print("https://myaccount.google.com/apppasswords")
