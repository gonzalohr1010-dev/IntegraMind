"""
Generador de Reportes Ejecutivos PDF para Integra Mind Energy
Crea reportes personalizados con análisis de ROI y proyecciones
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from datetime import datetime
import sqlite3

class ExecutiveReportGenerator:
    def __init__(self, db_path='energy_demo.db'):
        self.db_path = db_path
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
    
    def _create_custom_styles(self):
        """Crear estilos personalizados para el reporte"""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0284c7'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo
        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))
        
        # Texto destacado
        self.styles.add(ParagraphStyle(
            name='Highlight',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#0284c7'),
            fontName='Helvetica-Bold',
            spaceAfter=6
        ))
    
    def generate_report(self, client_name, industry="Energy", output_filename=None):
        """Generar reporte ejecutivo completo"""
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"reports/Executive_Report_{client_name.replace(' ', '_')}_{timestamp}.pdf"
        
        # Crear documento
        doc = SimpleDocTemplate(
            output_filename,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Contenedor de elementos
        story = []
        
        # Portada
        story.extend(self._create_cover_page(client_name, industry))
        story.append(PageBreak())
        
        # Resumen Ejecutivo
        story.extend(self._create_executive_summary(client_name, industry))
        story.append(Spacer(1, 0.3*inch))
        
        # Análisis de ROI
        story.extend(self._create_roi_analysis(client_name, industry))
        story.append(Spacer(1, 0.3*inch))
        
        # Módulos de IA
        story.extend(self._create_ai_modules_section())
        story.append(PageBreak())
        
        # Proyecciones
        story.extend(self._create_projections_section(industry))
        story.append(Spacer(1, 0.3*inch))
        
        # Próximos Pasos
        story.extend(self._create_next_steps())
        
        # Generar PDF
        doc.build(story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        
        return output_filename
    
    def _create_cover_page(self, client_name, industry):
        """Crear portada del reporte"""
        elements = []
        
        # Espaciado superior
        elements.append(Spacer(1, 2*inch))
        
        # Título
        title = Paragraph(
            "⚡ INTEGRA MIND ENERGY",
            self.styles['CustomTitle']
        )
        elements.append(title)
        elements.append(Spacer(1, 0.5*inch))
        
        # Subtítulo
        subtitle = Paragraph(
            f"Análisis Ejecutivo de Implementación<br/><b>{client_name}</b>",
            ParagraphStyle(
                name='CoverSubtitle',
                parent=self.styles['Normal'],
                fontSize=18,
                textColor=colors.HexColor('#64748b'),
                alignment=TA_CENTER,
                spaceAfter=12
            )
        )
        elements.append(subtitle)
        elements.append(Spacer(1, 0.3*inch))
        
        # Industria
        industry_text = Paragraph(
            f"Sector: <b>{industry}</b>",
            ParagraphStyle(
                name='Industry',
                parent=self.styles['Normal'],
                fontSize=14,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#0284c7')
            )
        )
        elements.append(industry_text)
        elements.append(Spacer(1, 1*inch))
        
        # Fecha
        date_text = Paragraph(
            datetime.now().strftime("%d de %B, %Y"),
            ParagraphStyle(
                name='Date',
                parent=self.styles['Normal'],
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#94a3b8')
            )
        )
        elements.append(date_text)
        
        return elements
    
    def _create_executive_summary(self, client_name, industry):
        """Crear resumen ejecutivo"""
        elements = []
        
        elements.append(Paragraph("Resumen Ejecutivo", self.styles['CustomSubtitle']))
        
        summary_text = f"""
        <b>Integra Mind Energy</b> presenta una solución de inteligencia artificial diseñada específicamente 
        para optimizar las operaciones de <b>{client_name}</b> en el sector {industry}. 
        <br/><br/>
        Nuestro sistema combina <b>tres módulos de IA</b> que trabajan en conjunto para:
        <br/>
        • Reducir pérdidas operacionales en un <b>15-20%</b><br/>
        • Prevenir fallas críticas antes de que ocurran<br/>
        • Detectar fraudes y anomalías en tiempo real<br/>
        • Optimizar el consumo energético y costos operativos
        <br/><br/>
        <b>Retorno de Inversión Proyectado:</b> 12-18 meses
        """
        
        elements.append(Paragraph(summary_text, self.styles['Normal']))
        
        return elements
    
    def _create_roi_analysis(self, client_name, industry):
        """Crear análisis de ROI"""
        elements = []
        
        elements.append(Paragraph("Análisis de Retorno de Inversión", self.styles['CustomSubtitle']))
        
        # Tabla de ahorros proyectados
        data = [
            ['Concepto', 'Ahorro Anual (USD)', 'Impacto'],
            ['Reducción de Pérdidas Técnicas', '$2,450,000', '15%'],
            ['Prevención de Fallas Críticas', '$1,800,000', '3 eventos evitados'],
            ['Detección de Fraude', '$950,000', '12 casos/año'],
            ['Optimización Operativa', '$1,200,000', '8% eficiencia'],
            ['', '', ''],
            ['TOTAL AHORRO ANUAL', '$6,400,000', '']
        ]
        
        table = Table(data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284c7')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.grey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 14),
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_ai_modules_section(self):
        """Crear sección de módulos de IA"""
        elements = []
        
        elements.append(Paragraph("Módulos de Inteligencia Artificial", self.styles['CustomSubtitle']))
        
        modules = [
            {
                'name': '🔮 Predicción de Demanda',
                'desc': 'Forecasting con 98% de precisión para optimizar generación y reducir costos.',
                'benefit': 'Ahorro: $45,000/día'
            },
            {
                'name': '🚨 Detección de Fraude',
                'desc': 'Identificación automática de consumos anómalos y manipulación de medidores.',
                'benefit': 'Recuperación: $950,000/año'
            },
            {
                'name': '🔧 Mantenimiento Predictivo',
                'desc': 'Prevención de fallas en transformadores y equipos críticos.',
                'benefit': 'Evita: $1.8M en paradas'
            }
        ]
        
        for module in modules:
            elements.append(Paragraph(module['name'], self.styles['Highlight']))
            elements.append(Paragraph(module['desc'], self.styles['Normal']))
            elements.append(Paragraph(f"<i>{module['benefit']}</i>", 
                ParagraphStyle(
                    name='Benefit',
                    parent=self.styles['Normal'],
                    fontSize=11,
                    textColor=colors.HexColor('#10b981'),
                    fontName='Helvetica-Oblique'
                )
            ))
            elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _create_projections_section(self, industry):
        """Crear sección de proyecciones"""
        elements = []
        
        elements.append(Paragraph("Proyección de Implementación", self.styles['CustomSubtitle']))
        
        timeline_data = [
            ['Fase', 'Duración', 'Entregables'],
            ['Fase 1: Piloto', '3 meses', 'Integración con sistemas existentes, capacitación'],
            ['Fase 2: Expansión', '6 meses', 'Despliegue completo, monitoreo 24/7'],
            ['Fase 3: Optimización', '3 meses', 'Ajuste fino, reportes ejecutivos']
        ]
        
        timeline_table = Table(timeline_data, colWidths=[1.5*inch, 1.5*inch, 3*inch])
        timeline_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ]))
        
        elements.append(timeline_table)
        
        return elements
    
    def _create_next_steps(self):
        """Crear sección de próximos pasos"""
        elements = []
        
        elements.append(Paragraph("Próximos Pasos", self.styles['CustomSubtitle']))
        
        next_steps_text = """
        <b>1. Reunión Técnica</b><br/>
        Presentación detallada de arquitectura y casos de uso específicos para su operación.
        <br/><br/>
        <b>2. Prueba de Concepto (PoC)</b><br/>
        Implementación piloto en un sector limitado para validar resultados (30 días).
        <br/><br/>
        <b>3. Propuesta Comercial</b><br/>
        Elaboración de contrato con métricas de éxito y garantías de ROI.
        <br/><br/>
        <b>Contacto:</b><br/>
        Email: sales@integramind.energy<br/>
        Tel: +54 11 XXXX-XXXX
        """
        
        elements.append(Paragraph(next_steps_text, self.styles['Normal']))
        
        return elements
    
    def _add_header_footer(self, canvas, doc):
        """Agregar encabezado y pie de página"""
        canvas.saveState()
        
        # Pie de página
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#94a3b8'))
        canvas.drawString(inch, 0.5*inch, f"Integra Mind Energy © {datetime.now().year}")
        canvas.drawRightString(doc.pagesize[0] - inch, 0.5*inch, f"Página {doc.page}")
        
        canvas.restoreState()


# Función de utilidad para generar reportes desde la API
def generate_client_report(client_name, industry="Energy", lead_id=None):
    """Generar reporte para un cliente específico"""
    import os
    
    # Crear directorio de reportes si no existe
    os.makedirs('reports', exist_ok=True)
    
    generator = ExecutiveReportGenerator()
    filename = generator.generate_report(client_name, industry)
    
    print(f"✅ Reporte generado: {filename}")
    return filename


if __name__ == "__main__":
    # Ejemplo de uso
    report_file = generate_client_report("Acme Energy Corp", "Energy & Utilities")
    print(f"Reporte creado en: {report_file}")
