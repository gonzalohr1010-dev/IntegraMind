"""
Domain Classifier - Detects user's domain from query context
"""
from typing import Dict, List
import re


class DomainClassifier:
    """Detects and manages domain-specific configurations."""
    
    DOMAINS = {
        'medical': {
            'keywords': ['surgery', 'patient', 'diagnosis', 'treatment', 'doctor', 'hospital', 
                        'valve', 'heart', 'operation', 'surgical', 'clinical', 'medical'],
            'weight': 1.0
        },
        'architecture': {
            'keywords': ['building', 'design', 'structure', 'blueprint', 'construction', 
                        'floor plan', 'architect', 'foundation', 'facade', 'renovation',
                        'interior', 'landscape', 'urban', 'sketch', 'elevation'],
            'weight': 1.0
        },
        'engineering': {
            'keywords': ['circuit', 'mechanical', 'system', 'analysis', 'engineering', 
                        'design', 'calculation', 'simulation', 'prototype', 'testing',
                        'stress', 'load', 'beam', 'torque', 'voltage', 'current',
                        'thermodynamics', 'fluid', 'aerodynamics', 'robotics'],
            'weight': 1.0
        },
        'legal': {
            'keywords': ['contract', 'case', 'law', 'regulation', 'court', 'attorney', 
                        'legal', 'lawsuit', 'compliance', 'statute'],
            'weight': 1.0
        },
        'government': {
            'keywords': ['policy', 'regulation', 'public', 'administration', 'government', 
                        'municipal', 'federal', 'legislation', 'civic', 'bureaucracy'],
            'weight': 1.0
        },
        'general': {
            'keywords': [],
            'weight': 0.1
        }
    }
    
    DOMAIN_CONFIGS = {
        'medical': {
            'primary_color': '#00ff00',
            'accent_color': '#00ffff',
            'terminology': {
                'steps': 'Procedure Steps',
                'data': 'Vitals',
                'context': 'Clinical Context'
            },
            'hud_layout': 'surgical',
            'icon': '🏥',
            'persona': 'Senior Surgeon & Medical Educator',
            'system_instruction': 'You are an expert medical professional. Provide precise, clinically accurate explanations using standard medical terminology. Focus on patient safety, anatomical correctness, and procedural details. When describing procedures, break them down into clear, actionable steps.'
        },
        'architecture': {
            'primary_color': '#ffa500',
            'accent_color': '#ffff00',
            'terminology': {
                'steps': 'Construction Phases',
                'data': 'Specifications',
                'context': 'Project Context'
            },
            'hud_layout': 'blueprint',
            'icon': '🏗️',
            'persona': 'Lead Architect & Design Visionary',
            'system_instruction': 'You are a visionary architect with deep technical knowledge. Balance aesthetic design principles with structural integrity and functionality. Use architectural terminology (e.g., facade, load-bearing, spatial flow). Focus on sustainability, user experience, and material selection.'
        },
        'engineering': {
            'primary_color': '#0080ff',
            'accent_color': '#00ffff',
            'terminology': {
                'steps': 'Process Steps',
                'data': 'Parameters',
                'context': 'Technical Context'
            },
            'hud_layout': 'technical',
            'icon': '⚙️',
            'persona': 'Chief Engineer & Systems Analyst',
            'system_instruction': 'You are a senior engineer. Provide rigorous, data-driven explanations. Focus on physics, mathematics, efficiency, and safety factors. Use precise units and technical specifications. When solving problems, show your work and logical derivation.'
        },
        'legal': {
            'primary_color': '#8b4513',
            'accent_color': '#daa520',
            'terminology': {
                'steps': 'Legal Steps',
                'data': 'Case Details',
                'context': 'Legal Context'
            },
            'hud_layout': 'formal',
            'icon': '⚖️',
            'persona': 'Senior Partner Attorney',
            'system_instruction': 'You are a seasoned attorney. Provide precise legal analysis citing relevant principles. Be objective, formal, and risk-aware. Distinguish between general legal information and specific advice. Use standard legal terminology (e.g., liability, precedent, clause).'
        },
        'government': {
            'primary_color': '#4169e1',
            'accent_color': '#ffffff',
            'terminology': {
                'steps': 'Policy Steps',
                'data': 'Metrics',
                'context': 'Policy Context'
            },
            'hud_layout': 'institutional',
            'icon': '🏛️',
            'persona': 'Public Policy Advisor',
            'system_instruction': 'You are a public policy expert. Focus on civic impact, regulations, and administrative processes. Be diplomatic, clear, and structured. Consider multiple stakeholders and long-term societal effects.'
        },
        'general': {
            'primary_color': '#00ffff',
            'accent_color': '#ffffff',
            'terminology': {
                'steps': 'Steps',
                'data': 'Data',
                'context': 'Context'
            },
            'hud_layout': 'default',
            'icon': '💡',
            'persona': 'Universal Assistant',
            'system_instruction': 'You are a helpful, intelligent assistant capable of adapting to any topic. Provide clear, concise, and accurate information. If a specific domain becomes apparent, adapt your style accordingly.'
        }
    }
    
    def classify(self, query: str, context: Dict = None) -> str:
        """
        Classifies the domain based on query and context.
        
        Args:
            query: User's question
            context: Additional context (user profile, previous queries, etc.)
            
        Returns:
            Domain name (e.g., 'medical', 'architecture')
        """
        query_lower = query.lower()
        scores = {}
        
        # Score each domain based on keyword matches
        for domain, config in self.DOMAINS.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in query_lower:
                    score += config['weight']
            scores[domain] = score
        
        # Check context for domain hints
        if context:
            if 'domain' in context:
                # Explicit domain from context
                return context['domain']
            if 'previous_domain' in context:
                prev = context['previous_domain']
                if prev in scores and scores[prev] > 0:
                    # Boost previous domain if there's any match
                    scores[prev] *= 1.5
        
        # Return domain with highest score, or 'general' if no matches
        max_domain = max(scores.items(), key=lambda x: x[1])
        return max_domain[0] if max_domain[1] > 0 else 'general'
    
    def get_domain_config(self, domain: str) -> Dict:
        """
        Returns domain-specific configuration.
        
        Args:
            domain: Domain name
            
        Returns:
            Configuration dictionary with colors, terminology, etc.
        """
        return self.DOMAIN_CONFIGS.get(domain, self.DOMAIN_CONFIGS['general'])
    
    def get_all_domains(self) -> List[str]:
        """Returns list of all supported domains."""
        return [d for d in self.DOMAINS.keys() if d != 'general']
