"""
Content Generator - Multi-modal content generation system
Generates images, videos, and animations for Experience Objects
"""
import os
import json
import asyncio
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Generates multi-modal content for experiences using AI and procedural methods."""
    
    # Content generation strategies
    STRATEGIES = {
        'static_images': 'generate_images',
        'animated_sequence': 'generate_image_sequence',
        '360_video': 'generate_360_panorama',
        '3d_model': 'load_or_generate_model',
        'hologram': 'generate_hologram_data'
    }
    
    def __init__(self, asset_manager=None, image_generator=None):
        """
        Initialize Content Generator.
        
        Args:
            asset_manager: AssetManager instance for storing generated content
            image_generator: Optional custom image generation function
        """
        self.asset_manager = asset_manager
        self.image_generator = image_generator
        
        # Check for available generation backends
        self.available_backends = self._detect_backends()
        logger.info(f"Content Generator initialized with backends: {self.available_backends}")
    
    def _detect_backends(self) -> Dict[str, bool]:
        """Detect available content generation backends."""
        backends = {
            'internal_image': True,  # Always available (uses generate_image tool)
            'runway': os.getenv('RUNWAY_API_KEY') is not None,
            'luma': os.getenv('LUMA_API_KEY') is not None,
            'stability': os.getenv('STABILITY_API_KEY') is not None,
            'replicate': os.getenv('REPLICATE_API_TOKEN') is not None
        }
        return backends
    
    def generate_for_experience(
        self, 
        experience: Dict,
        domain: str = 'general'
    ) -> Dict[str, List[str]]:
        """
        Generate all content for an Experience Object.
        
        Args:
            experience: Experience Object dictionary
            domain: Domain context for generation
            
        Returns:
            Dictionary mapping content types to asset IDs
        """
        viz_type = experience.get('visualization_type', 'static_images')
        steps = experience.get('steps', experience.get('action_plan', []))
        
        if not steps:
            logger.warning("No steps found in experience")
            return {}
        
        # Determine generation strategy
        strategy = self.STRATEGIES.get(viz_type, 'generate_images')
        
        logger.info(f"Generating content for {len(steps)} steps using strategy: {strategy}")
        
        # Generate content based on strategy
        if strategy == 'generate_images':
            return self._generate_static_images(steps, domain, experience)
        elif strategy == 'generate_image_sequence':
            return self._generate_animated_sequence(steps, domain, experience)
        elif strategy == 'generate_360_panorama':
            return self._generate_360_content(steps, domain, experience)
        else:
            logger.warning(f"Strategy {strategy} not yet implemented")
            return {}
    
    def _generate_static_images(
        self, 
        steps: List[Any],
        domain: str,
        experience: Dict
    ) -> Dict[str, List[str]]:
        """Generate static images for each step."""
        asset_ids = []
        
        # Get domain-specific styling
        style_prompt = self._get_domain_style(domain)
        context = experience.get('title', 'Procedure')
        
        for i, step in enumerate(steps):
            # Extract step description
            if isinstance(step, dict):
                step_desc = step.get('description', step.get('title', str(step)))
            else:
                step_desc = str(step)
            
            # Build generation prompt
            prompt = self._build_image_prompt(
                context=context,
                step_description=step_desc,
                step_number=i + 1,
                domain=domain,
                style=style_prompt
            )
            
            # Generate image
            try:
                asset_id = self._generate_single_image(
                    prompt=prompt,
                    domain=domain,
                    experience_id=experience.get('id', 'unknown'),
                    step_index=i
                )
                
                if asset_id:
                    asset_ids.append(asset_id)
                    logger.info(f"Generated image for step {i+1}/{len(steps)}")
                
            except Exception as e:
                logger.error(f"Error generating image for step {i}: {e}")
        
        return {'images': asset_ids}
    
    def _generate_animated_sequence(
        self,
        steps: List[Any],
        domain: str,
        experience: Dict
    ) -> Dict[str, List[str]]:
        """Generate an animated sequence (series of images or video)."""
        # For now, generate images and return them as a sequence
        # Future: Use video generation API
        
        result = self._generate_static_images(steps, domain, experience)
        
        # If video generation is available, create transitions
        if self.available_backends.get('runway') or self.available_backends.get('luma'):
            logger.info("Video generation available but not yet implemented")
            # TODO: Implement video generation from image sequence
        
        return result
    
    def _generate_360_content(
        self,
        steps: List[Any],
        domain: str,
        experience: Dict
    ) -> Dict[str, List[str]]:
        """Generate 360° panoramic content."""
        # Placeholder for 360° generation
        logger.warning("360° content generation not yet implemented")
        
        # For now, generate regular images
        # Future: Use specialized 360° generation APIs
        return self._generate_static_images(steps, domain, experience)
    
    def _generate_single_image(
        self,
        prompt: str,
        domain: str,
        experience_id: str,
        step_index: int
    ) -> Optional[str]:
        """
        Generate a single image using available backend.
        
        Args:
            prompt: Image generation prompt
            domain: Domain context
            experience_id: Associated experience ID
            step_index: Step number
            
        Returns:
            Asset ID or None
        """
        # Use custom generator if provided
        if self.image_generator:
            try:
                image_path = self.image_generator(prompt)
                
                # Store in asset manager if available
                if self.asset_manager and os.path.exists(image_path):
                    asset_id = self.asset_manager.store_asset(
                        file_path=image_path,
                        domain=domain,
                        experience_id=experience_id,
                        metadata={
                            'step_index': step_index,
                            'prompt': prompt[:200]
                        }
                    )
                    return asset_id
                
            except Exception as e:
                logger.error(f"Error with custom image generator: {e}")
        
        # Fallback: Log that image generation is needed
        logger.info(f"Image generation needed: {prompt[:100]}...")
        return None
    
    def _build_image_prompt(
        self,
        context: str,
        step_description: str,
        step_number: int,
        domain: str,
        style: str
    ) -> str:
        """Build a detailed prompt for image generation."""
        
        # Domain-specific prompt templates
        templates = {
            'medical': "Medical illustration: {context}. Step {step_number}: {step_description}. {style}",
            'architecture': "Architectural visualization: {context}. Phase {step_number}: {step_description}. {style}",
            'engineering': "Technical diagram: {context}. Step {step_number}: {step_description}. {style}",
            'legal': "Professional diagram: {context}. Step {step_number}: {step_description}. {style}",
            'government': "Policy visualization: {context}. Step {step_number}: {step_description}. {style}",
            'general': "{context}. Step {step_number}: {step_description}. {style}"
        }
        
        template = templates.get(domain, templates['general'])
        
        return template.format(
            context=context,
            step_number=step_number,
            step_description=step_description,
            style=style
        )
    
    def _get_domain_style(self, domain: str) -> str:
        """Get domain-specific style guidelines for image generation."""
        
        styles = {
            'medical': "Clinical photography style with proper medical lighting, sterile environment, anatomical accuracy, professional medical illustration quality.",
            'architecture': "Professional architectural rendering, clean lines, realistic materials, proper lighting and shadows, blueprint aesthetic.",
            'engineering': "Technical illustration style, precise measurements, cross-sections visible, engineering diagram quality, CAD-like precision.",
            'legal': "Professional business style, clean and formal, document-like presentation, corporate aesthetic.",
            'government': "Institutional style, formal and authoritative, clear and accessible, public service aesthetic.",
            'general': "Clear, professional, and informative visual style."
        }
        
        return styles.get(domain, styles['general'])
    
    def generate_step_video(
        self,
        step_description: str,
        domain: str,
        duration: int = 5
    ) -> Optional[str]:
        """
        Generate a short video for a single step.
        
        Args:
            step_description: Description of the step
            domain: Domain context
            duration: Video duration in seconds
            
        Returns:
            Asset ID or None
        """
        # Check for video generation backends
        if not (self.available_backends.get('runway') or self.available_backends.get('luma')):
            logger.warning("No video generation backend available")
            return None
        
        # Placeholder for video generation
        logger.info(f"Video generation requested: {step_description[:50]}...")
        
        # TODO: Implement actual video generation
        # - Use Runway Gen-3 API
        # - Use Luma Dream Machine API
        # - Store result in asset manager
        
        return None
    
    def generate_3d_model(
        self,
        description: str,
        domain: str
    ) -> Optional[str]:
        """
        Generate or load a 3D model.
        
        Args:
            description: Description of the object
            domain: Domain context
            
        Returns:
            Asset ID or None
        """
        # Placeholder for 3D model generation/loading
        logger.info(f"3D model requested: {description[:50]}...")
        
        # TODO: Implement 3D model generation/loading
        # - Use Meshy API for 3D generation
        # - Load from model libraries
        # - Convert formats if needed
        
        return None
    
    def batch_generate(
        self,
        experiences: List[Dict],
        domain: str = 'general'
    ) -> Dict[str, Dict]:
        """
        Generate content for multiple experiences in batch.
        
        Args:
            experiences: List of Experience Objects
            domain: Domain context
            
        Returns:
            Dictionary mapping experience IDs to generated content
        """
        results = {}
        
        for exp in experiences:
            exp_id = exp.get('id', exp.get('title', 'unknown'))
            try:
                content = self.generate_for_experience(exp, domain)
                results[exp_id] = content
                logger.info(f"Generated content for experience: {exp_id}")
            except Exception as e:
                logger.error(f"Error generating content for {exp_id}: {e}")
                results[exp_id] = {'error': str(e)}
        
        return results
