import React, { useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer';
import axios from 'axios';

function MoleculeViewer() {
  const { smiles } = useParams();
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const labelRendererRef = useRef(null);
  const controlsRef = useRef(null);

  useEffect(() => {
    initScene();
    loadMolecule();

    return () => {
      if (rendererRef.current) {
        rendererRef.current.dispose();
      }
      if (labelRendererRef.current) {
        labelRendererRef.current.dispose();
      }
    };
  }, [smiles]);

  const initScene = () => {
    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111122);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, mountRef.current.clientWidth / mountRef.current.clientHeight, 0.1, 1000);
    camera.position.set(10, 10, 10);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Label Renderer
    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    labelRenderer.domElement.style.position = 'absolute';
    labelRenderer.domElement.style.top = '0px';
    labelRenderer.domElement.style.left = '0px';
    labelRenderer.domElement.style.pointerEvents = 'none';
    mountRef.current.appendChild(labelRenderer.domElement);
    labelRendererRef.current = labelRenderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.0;
    controlsRef.current = controls;

    // Lights
    const ambientLight = new THREE.AmbientLight(0x404060);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
    directionalLight.position.set(1, 1, 1);
    scene.add(directionalLight);

    const backLight = new THREE.DirectionalLight(0x446688, 0.5);
    backLight.position.set(-1, -1, -1);
    scene.add(backLight);

    // Grid helper
    const gridHelper = new THREE.GridHelper(20, 20, 0x3399ff, 0x224466);
    scene.add(gridHelper);

    // Axis helper
    const axesHelper = new THREE.AxesHelper(5);
    scene.add(axesHelper);

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);

      controls.update();

      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
    };
    animate();

    // Handle resize
    const handleResize = () => {
      camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
      labelRenderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  };

  const loadMolecule = async () => {
    try {
      // Fetch 3D structure from PubChem
      const response = await axios.get(
        `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/${encodeURIComponent(smiles)}/3d/JSON`
      );
      
      const atoms = response.data.PC_Compounds[0].atoms;
      const bonds = response.data.PC_Compounds[0].bonds;
      
      createMoleculeModel(atoms, bonds);
    } catch (error) {
      console.error('Error loading molecule:', error);
      // Create a fallback molecule
      createFallbackMolecule();
    }
  };

  const createMoleculeModel = (atoms, bonds) => {
    const scene = sceneRef.current;
    
    // Atom colors (CPK coloring)
    const colors = {
      1: 0xffffff,  // H - white
      6: 0x333333,  // C - dark gray
      7: 0x3050F8,  // N - blue
      8: 0xFF0D0D,  // O - red
      9: 0x90E050,  // F - green
      15: 0xFF8000, // P - orange
      16: 0xFFFF30, // S - yellow
      17: 0x1FF01F, // Cl - green
      35: 0xA62929, // Br - brown
      53: 0x470047  // I - purple
    };

    // Create atoms
    const atomGroup = new THREE.Group();
    const atomPositions = [];

    atoms.aid.forEach((aid, index) => {
      const element = atoms.element[index];
      const x = atoms.x ? atoms.x[index] : (Math.random() - 0.5) * 5;
      const y = atoms.y ? atoms.y[index] : (Math.random() - 0.5) * 5;
      const z = atoms.z ? atoms.z[index] : (Math.random() - 0.5) * 5;
      
      atomPositions[aid] = new THREE.Vector3(x, y, z);

      // Sphere for atom
      const radius = getAtomicRadius(element);
      const color = colors[element] || 0xCCCCCC;
      
      const geometry = new THREE.SphereGeometry(radius, 32, 16);
      const material = new THREE.MeshPhongMaterial({ 
        color: color,
        shininess: 30,
        emissive: 0x000000
      });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.set(x, y, z);
      atomGroup.add(sphere);

      // Label for atom
      const div = document.createElement('div');
      div.textContent = getElementSymbol(element);
      div.style.color = 'white';
      div.style.fontSize = '16px';
      div.style.fontWeight = 'bold';
      div.style.textShadow = '1px 1px 2px black';
      
      const label = new CSS2DObject(div);
      label.position.set(x, y + radius + 0.3, z);
      atomGroup.add(label);
    });

    scene.add(atomGroup);

    // Create bonds
    const bondGroup = new THREE.Group();
    
    bonds.aid1.forEach((aid1, index) => {
      const aid2 = bonds.aid2[index];
      const bondType = bonds.order ? bonds.order[index] : 1;
      
      const pos1 = atomPositions[aid1];
      const pos2 = atomPositions[aid2];
      
      if (pos1 && pos2) {
        createBond(bondGroup, pos1, pos2, bondType);
      }
    });

    scene.add(bondGroup);
  };

  const createBond = (group, pos1, pos2, bondType) => {
    const direction = new THREE.Vector3().subVectors(pos2, pos1);
    const length = direction.length();
    
    // Cylinder for bond
    const cylinder = new THREE.Mesh(
      new THREE.CylinderGeometry(0.1, 0.1, length, 8),
      new THREE.MeshPhongMaterial({ color: 0xCCCCCC })
    );
    
    // Position cylinder
    const midPoint = new THREE.Vector3().addVectors(pos1, pos2).multiplyScalar(0.5);
    cylinder.position.copy(midPoint);
    
    // Orient cylinder
    cylinder.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      direction.clone().normalize()
    );
    
    group.add(cylinder);

    // For double bonds, add a second cylinder offset
    if (bondType >= 2) {
      const offset = new THREE.Vector3().crossVectors(direction, new THREE.Vector3(0, 1, 0)).normalize();
      if (offset.length() < 0.1) {
        offset.set(1, 0, 0);
      }
      
      const cylinder2 = new THREE.Mesh(
        new THREE.CylinderGeometry(0.1, 0.1, length, 8),
        new THREE.MeshPhongMaterial({ color: 0xCCCCCC })
      );
      
      const offsetPos1 = pos1.clone().add(offset.clone().multiplyScalar(0.2));
      const offsetPos2 = pos2.clone().add(offset.clone().multiplyScalar(0.2));
      const offsetMid = new THREE.Vector3().addVectors(offsetPos1, offsetPos2).multiplyScalar(0.5);
      
      cylinder2.position.copy(offsetMid);
      cylinder2.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        direction.clone().normalize()
      );
      
      group.add(cylinder2);
    }
  };

  const createFallbackMolecule = () => {
    const scene = sceneRef.current;
    
    // Create a benzene ring as fallback
    const radius = 1.4;
    const points = [];
    for (let i = 0; i < 6; i++) {
      const angle = (i / 6) * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      points.push(new THREE.Vector3(x, 0, z));
    }

    // Carbon atoms
    points.forEach((pos, i) => {
      const geometry = new THREE.SphereGeometry(0.4, 32);
      const material = new THREE.MeshPhongMaterial({ color: 0x333333 });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.copy(pos);
      scene.add(sphere);

      // Label
      const div = document.createElement('div');
      div.textContent = 'C';
      div.style.color = 'white';
      div.style.fontSize = '16px';
      const label = new CSS2DObject(div);
      label.position.copy(pos.clone().add(new THREE.Vector3(0, 0.5, 0)));
      scene.add(label);
    });

    // Bonds
    for (let i = 0; i < 6; i++) {
      const pos1 = points[i];
      const pos2 = points[(i + 1) % 6];
      
      const direction = new THREE.Vector3().subVectors(pos2, pos1);
      const length = direction.length();
      
      const cylinder = new THREE.Mesh(
        new THREE.CylinderGeometry(0.15, 0.15, length, 8),
        new THREE.MeshPhongMaterial({ color: 0xCCCCCC })
      );
      
      const midPoint = new THREE.Vector3().addVectors(pos1, pos2).multiplyScalar(0.5);
      cylinder.position.copy(midPoint);
      cylinder.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        direction.clone().normalize()
      );
      
      scene.add(cylinder);
    }
  };

  const getAtomicRadius = (element) => {
    const radii = {
      1: 0.3,   // H
      6: 0.4,   // C
      7: 0.35,  // N
      8: 0.35,  // O
      9: 0.3,   // F
      15: 0.45, // P
      16: 0.45, // S
      17: 0.5,  // Cl
      35: 0.55, // Br
      53: 0.6   // I
    };
    return radii[element] || 0.4;
  };

  const getElementSymbol = (element) => {
    const symbols = {
      1: 'H', 6: 'C', 7: 'N', 8: 'O', 9: 'F',
      15: 'P', 16: 'S', 17: 'Cl', 35: 'Br', 53: 'I'
    };
    return symbols[element] || '?';
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3>3D Molecule Viewer</h3>
        <div>
          <button 
            className="btn btn-sm btn-outline-primary me-2"
            onClick={() => controlsRef.current.autoRotate = !controlsRef.current.autoRotate}
          >
            Toggle Rotate
          </button>
          <button 
            className="btn btn-sm btn-outline-secondary"
            onClick={() => {
              cameraRef.current.position.set(10, 10, 10);
              controlsRef.current.target.set(0, 0, 0);
              controlsRef.current.update();
            }}
          >
            Reset View
          </button>
        </div>
      </div>
      
      <div 
        ref={mountRef} 
        style={{ 
          width: '100%', 
          height: '600px', 
          position: 'relative',
          background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
          borderRadius: '8px',
          overflow: 'hidden'
        }}
      />
      
      <div className="mt-3">
        <h5>Molecule Information</h5>
        <div className="card">
          <div className="card-body">
            <p><strong>SMILES:</strong> <code>{decodeURIComponent(smiles)}</code></p>
            <p><strong>Formula:</strong> (Calculated from structure)</p>
            <p><strong>Molecular Weight:</strong> (Calculated from structure)</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MoleculeViewer;