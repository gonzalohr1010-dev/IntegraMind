// Advanced Visualization Engine - Universal Renderer
// Supports: Images, Videos, 360° Panoramas, 3D Models, Holographic Data

class UniversalRenderer {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.currentContent = null;
        this.contentType = null;
        this.animationId = null;

        // Content-specific objects
        this.videoElement = null;
        this.modelLoader = null;
        this.currentModel = null;

        this.init();
    }

    init() {
        // Setup Three.js scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x050a14);

        // Setup camera
        this.camera = new THREE.PerspectiveCamera(
            75,
            window.innerWidth / window.innerHeight,
            0.1,
            1000
        );
        this.camera.position.z = 3;

        // Setup renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.domElement.style.position = 'absolute';
        this.renderer.domElement.style.top = '0';
        this.renderer.domElement.style.left = '0';
        this.renderer.domElement.style.zIndex = '1';
        this.container.appendChild(this.renderer.domElement);

        // Setup orbit controls for interaction
        if (typeof THREE.OrbitControls !== 'undefined') {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
        }

        // Add lights
        this.setupLights();

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());

        // Start animation loop
        this.animate();
    }

    setupLights() {
        const ambientLight = new THREE.AmbientLight(0x404040, 2);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(5, 5, 5);
        this.scene.add(directionalLight);
    }

    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());

        // Update controls
        if (this.controls) {
            this.controls.update();
        }

        // Content-specific animations
        if (this.currentContent) {
            this.updateContent();
        }

        this.renderer.render(this.scene, this.camera);
    }

    updateContent() {
        const time = Date.now() * 0.001;

        if (this.contentType === 'image' || this.contentType === 'video') {
            // Gentle floating animation for billboards
            if (this.currentContent) {
                this.currentContent.position.y = Math.sin(time * 0.5) * 0.1;
                this.currentContent.rotation.y = Math.sin(time * 0.3) * 0.05;
            }
        } else if (this.contentType === '3d_model') {
            // Rotate 3D models slowly
            if (this.currentModel) {
                this.currentModel.rotation.y = time * 0.3;
            }
        }
    }

    // ========================================================================
    // CONTENT LOADING METHODS
    // ========================================================================

    loadContent(asset) {
        // Clear previous content
        this.clearContent();

        const type = asset.type;
        const url = asset.url;

        console.log(`Loading ${type} content: ${url}`);

        switch (type) {
            case 'image':
                this.loadImage(url);
                break;
            case 'video':
                this.loadVideo(url);
                break;
            case '360_video':
                this.load360Video(url);
                break;
            case '3d_model':
                this.load3DModel(url);
                break;
            default:
                console.warn(`Unsupported content type: ${type}`);
        }
    }

    loadImage(url) {
        this.contentType = 'image';

        const loader = new THREE.TextureLoader();
        loader.load(url, (texture) => {
            const geometry = new THREE.PlaneGeometry(4, 3);
            const material = new THREE.MeshBasicMaterial({
                map: texture,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.95
            });

            const mesh = new THREE.Mesh(geometry, material);
            this.scene.add(mesh);
            this.currentContent = mesh;

            // Add glowing border
            this.addBorder(mesh, 4.1, 3.1);

            // Fade in effect
            mesh.material.opacity = 0;
            this.fadeIn(mesh.material);
        }, undefined, (error) => {
            console.error('Error loading image:', error);
        });
    }

    loadVideo(url) {
        this.contentType = 'video';

        // Create video element
        const video = document.createElement('video');
        video.src = url;
        video.loop = true;
        video.muted = true;
        video.play();
        this.videoElement = video;

        // Create texture from video
        const texture = new THREE.VideoTexture(video);
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;

        const geometry = new THREE.PlaneGeometry(4, 3);
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.95
        });

        const mesh = new THREE.Mesh(geometry, material);
        this.scene.add(mesh);
        this.currentContent = mesh;

        // Add border
        this.addBorder(mesh, 4.1, 3.1);

        // Add video controls overlay
        this.addVideoControls(video);
    }

    load360Video(url) {
        this.contentType = '360_video';

        // Create video element
        const video = document.createElement('video');
        video.src = url;
        video.loop = true;
        video.muted = true;
        video.play();
        this.videoElement = video;

        // Create 360° sphere (inverted normals for inside view)
        const geometry = new THREE.SphereGeometry(500, 60, 40);
        geometry.scale(-1, 1, 1); // Invert for inside view

        const texture = new THREE.VideoTexture(video);
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;

        const material = new THREE.MeshBasicMaterial({ map: texture });
        const sphere = new THREE.Mesh(geometry, material);

        this.scene.add(sphere);
        this.currentContent = sphere;

        // Enable full rotation for 360° viewing
        if (this.controls) {
            this.controls.enablePan = false;
            this.controls.minDistance = 1;
            this.controls.maxDistance = 100;
        }

        // Reset camera position for 360° view
        this.camera.position.set(0, 0, 0.1);

        // Add 360° indicator
        this.add360Indicator();
    }

    load3DModel(url) {
        this.contentType = '3d_model';

        // Determine loader based on file extension
        const ext = url.split('.').pop().toLowerCase();

        if (ext === 'gltf' || ext === 'glb') {
            this.loadGLTF(url);
        } else if (ext === 'obj') {
            this.loadOBJ(url);
        } else {
            console.warn(`Unsupported 3D model format: ${ext}`);
        }
    }

    loadGLTF(url) {
        if (typeof THREE.GLTFLoader === 'undefined') {
            console.error('GLTFLoader not available');
            return;
        }

        const loader = new THREE.GLTFLoader();
        loader.load(url, (gltf) => {
            const model = gltf.scene;

            // Center and scale model
            const box = new THREE.Box3().setFromObject(model);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());

            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 2 / maxDim;
            model.scale.multiplyScalar(scale);

            model.position.sub(center.multiplyScalar(scale));

            this.scene.add(model);
            this.currentModel = model;
            this.currentContent = model;

            // Add model info overlay
            this.addModelInfo(gltf);

        }, undefined, (error) => {
            console.error('Error loading GLTF model:', error);
        });
    }

    loadOBJ(url) {
        if (typeof THREE.OBJLoader === 'undefined') {
            console.error('OBJLoader not available');
            return;
        }

        const loader = new THREE.OBJLoader();
        loader.load(url, (obj) => {
            // Similar processing as GLTF
            this.scene.add(obj);
            this.currentModel = obj;
            this.currentContent = obj;
        }, undefined, (error) => {
            console.error('Error loading OBJ model:', error);
        });
    }

    // ========================================================================
    // UI ENHANCEMENTS
    // ========================================================================

    addBorder(mesh, width, height) {
        const borderGeometry = new THREE.PlaneGeometry(width, height);
        const borderMaterial = new THREE.MeshBasicMaterial({
            color: 0x00ffff,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const border = new THREE.Mesh(borderGeometry, borderMaterial);
        border.position.z = -0.01;
        mesh.add(border);
    }

    fadeIn(material, duration = 500) {
        const startTime = Date.now();
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            material.opacity = progress * 0.95;

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        animate();
    }

    addVideoControls(video) {
        // Create simple play/pause overlay
        const controlsDiv = document.createElement('div');
        controlsDiv.style.position = 'fixed';
        controlsDiv.style.bottom = '100px';
        controlsDiv.style.left = '50%';
        controlsDiv.style.transform = 'translateX(-50%)';
        controlsDiv.style.zIndex = '15';
        controlsDiv.style.background = 'rgba(0,0,0,0.7)';
        controlsDiv.style.padding = '10px 20px';
        controlsDiv.style.borderRadius = '20px';
        controlsDiv.style.color = '#00ffff';
        controlsDiv.style.cursor = 'pointer';
        controlsDiv.textContent = '⏸ Pause';

        controlsDiv.onclick = () => {
            if (video.paused) {
                video.play();
                controlsDiv.textContent = '⏸ Pause';
            } else {
                video.pause();
                controlsDiv.textContent = '▶ Play';
            }
        };

        document.body.appendChild(controlsDiv);
        this.videoControls = controlsDiv;
    }

    add360Indicator() {
        const indicator = document.createElement('div');
        indicator.style.position = 'fixed';
        indicator.style.top = '100px';
        indicator.style.left = '50%';
        indicator.style.transform = 'translateX(-50%)';
        indicator.style.zIndex = '15';
        indicator.style.background = 'rgba(0,255,255,0.2)';
        indicator.style.padding = '10px 20px';
        indicator.style.borderRadius = '20px';
        indicator.style.color = '#00ffff';
        indicator.style.border = '1px solid #00ffff';
        indicator.textContent = '🌐 360° View - Drag to look around';

        document.body.appendChild(indicator);
        this.indicator360 = indicator;
    }

    addModelInfo(gltf) {
        const info = document.createElement('div');
        info.style.position = 'fixed';
        info.style.top = '100px';
        info.style.right = '20px';
        info.style.zIndex = '15';
        info.style.background = 'rgba(0,0,0,0.7)';
        info.style.padding = '15px';
        info.style.borderRadius = '8px';
        info.style.color = '#fff';
        info.style.fontSize = '0.9rem';
        info.style.maxWidth = '200px';

        const animations = gltf.animations ? gltf.animations.length : 0;
        info.innerHTML = `
            <div style="color: #00ffff; margin-bottom: 5px;">3D Model Info</div>
            <div>Animations: ${animations}</div>
            <div style="margin-top: 10px; font-size: 0.8rem; color: #aaa;">
                Drag to rotate<br>
                Scroll to zoom
            </div>
        `;

        document.body.appendChild(info);
        this.modelInfo = info;
    }

    // ========================================================================
    // CLEANUP
    // ========================================================================

    clearContent() {
        // Remove current content from scene
        if (this.currentContent) {
            this.scene.remove(this.currentContent);

            // Dispose geometries and materials
            if (this.currentContent.geometry) {
                this.currentContent.geometry.dispose();
            }
            if (this.currentContent.material) {
                if (this.currentContent.material.map) {
                    this.currentContent.material.map.dispose();
                }
                this.currentContent.material.dispose();
            }

            this.currentContent = null;
        }

        // Stop video if playing
        if (this.videoElement) {
            this.videoElement.pause();
            this.videoElement = null;
        }

        // Remove UI overlays
        if (this.videoControls) {
            this.videoControls.remove();
            this.videoControls = null;
        }
        if (this.indicator360) {
            this.indicator360.remove();
            this.indicator360 = null;
        }
        if (this.modelInfo) {
            this.modelInfo.remove();
            this.modelInfo = null;
        }

        // Reset camera for non-360 content
        if (this.contentType === '360_video') {
            this.camera.position.set(0, 0, 3);
            if (this.controls) {
                this.controls.reset();
            }
        }
    }

    cleanup() {
        this.clearContent();

        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }

        if (this.renderer) {
            this.renderer.dispose();
            if (this.renderer.domElement && this.renderer.domElement.parentNode) {
                this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
            }
        }

        if (this.controls) {
            this.controls.dispose();
        }

        window.removeEventListener('resize', () => this.onWindowResize());
    }
}

// ============================================================================
// GLOBAL API
// ============================================================================

let globalRenderer = null;

window.initUniversalRenderer = function (container) {
    if (globalRenderer) {
        globalRenderer.cleanup();
    }
    globalRenderer = new UniversalRenderer(container);
    return globalRenderer;
};

window.loadVisualizationContent = function (asset) {
    if (!globalRenderer) {
        console.error('Renderer not initialized');
        return;
    }
    globalRenderer.loadContent(asset);
};

window.cleanupRenderer = function () {
    if (globalRenderer) {
        globalRenderer.cleanup();
        globalRenderer = null;
    }
};
