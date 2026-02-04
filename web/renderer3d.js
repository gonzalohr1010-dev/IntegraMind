// Surgical Reality Weaver - 3D Image Renderer

let scene, camera, renderer;
let imageBoard; // Billboard to display surgical images
let animationId;
let currentStepImages = [];

function initSurgicalScene(container) {
    // Hide the placeholder grid
    const placeholder = document.getElementById('placeholder-grid');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    // 1. Setup Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050a14);

    // 2. Setup Camera
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 3;

    // 3. Setup Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.domElement.style.position = 'absolute';
    renderer.domElement.style.top = '0';
    renderer.domElement.style.left = '0';
    renderer.domElement.style.zIndex = '1';
    container.appendChild(renderer.domElement);

    // 4. Add Lights
    const ambientLight = new THREE.AmbientLight(0x404040, 2);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    // 5. Create Image Billboard
    createImageBoard();

    // 6. Start Animation Loop
    animate();

    // 7. Handle window resize
    window.addEventListener('resize', onWindowResize);
}

function createImageBoard() {
    // Create a plane to display images
    const geometry = new THREE.PlaneGeometry(4, 3);
    const material = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.95
    });
    imageBoard = new THREE.Mesh(geometry, material);
    scene.add(imageBoard);

    // Add a glowing border effect
    const borderGeometry = new THREE.PlaneGeometry(4.1, 3.1);
    const borderMaterial = new THREE.MeshBasicMaterial({
        color: 0x00ffff,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide
    });
    const border = new THREE.Mesh(borderGeometry, borderMaterial);
    border.position.z = -0.01;
    imageBoard.add(border);
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    animationId = requestAnimationFrame(animate);

    // Gentle floating animation
    if (imageBoard) {
        const time = Date.now() * 0.001;
        imageBoard.position.y = Math.sin(time * 0.5) * 0.1;
        imageBoard.rotation.y = Math.sin(time * 0.3) * 0.05;
    }

    renderer.render(scene, camera);
}

// API to update the displayed image based on step
window.updateSurgical3D = function (stepIndex, action) {
    if (!imageBoard) return;

    // Map step index to image file
    const imageFiles = [
        '/static/surgical_steps/step_1_incision_1764797461842.png',
        '/static/surgical_steps/step_2_retraction_1764797476417.png',
        '/static/surgical_steps/step_3_excision_1764797492378.png',
        '/static/surgical_steps/step_4_valve_placement_1764797506057.png',
        '/static/surgical_steps/step_5_suturing_1764797520116.png',
        '/static/surgical_steps/step_6_closure_1764797535553.png'
    ];

    if (stepIndex >= 0 && stepIndex < imageFiles.length) {
        const loader = new THREE.TextureLoader();
        loader.load(imageFiles[stepIndex], (texture) => {
            imageBoard.material.map = texture;
            imageBoard.material.needsUpdate = true;

            // Add a brief flash effect on change
            imageBoard.material.opacity = 0.5;
            setTimeout(() => {
                imageBoard.material.opacity = 0.95;
            }, 200);
        });
    }
};

window.cleanup3D = function () {
    if (animationId) cancelAnimationFrame(animationId);
    if (renderer) {
        renderer.dispose();
        const canvas = renderer.domElement;
        if (canvas && canvas.parentNode) {
            canvas.parentNode.removeChild(canvas);
        }
    }
    if (scene) {
        scene.traverse(object => {
            if (object.geometry) object.geometry.dispose();
            if (object.material) {
                if (object.material.map) object.material.map.dispose();
                object.material.dispose();
            }
        });
    }
    window.removeEventListener('resize', onWindowResize);
};
