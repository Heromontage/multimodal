'use client';
import {useEffect, useRef, useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {OBJLoader} from 'three/addons/loaders/OBJLoader.js';
import {Results, Target} from '@/lib/types';
import {arteryColors} from '@/lib/arteryColors';

type Asset={file:string;name:string;target:Target|null};
export default function HeartViewer({target,results,resetKey,transparent,onSelect}:{target:Target;results:Results|null;resetKey:number;transparent:boolean;onSelect:(t:Target)=>void}){
  const mount=useRef<HTMLDivElement>(null);
  const sceneRef=useRef<{meshes:THREE.Mesh[];controls:OrbitControls;render:()=>void;focus:(target:Target)=>void}|null>(null);
  const callback=useRef(onSelect);
  const [status,setStatus]=useState('Loading BodyParts3D anatomy…');
  const [failed,setFailed]=useState(false);
  callback.current=onSelect;
  useEffect(()=>{
    if(!mount.current)return;
    const element=mount.current;let disposed=false;
    const scene=new THREE.Scene();
    let renderer:THREE.WebGLRenderer;
    try{renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});}
    catch{setStatus('3D rendering is unavailable. Vessel predictions remain available alongside the viewer.');setFailed(true);return;}
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
    renderer.setClearColor(0,0);renderer.outputColorSpace=THREE.SRGBColorSpace;
    element.appendChild(renderer.domElement);
    const camera=new THREE.PerspectiveCamera(34,1,.01,100);
    camera.position.set(0,.15,6.8);
    const controls=new OrbitControls(camera,renderer.domElement);
    controls.enablePan=false;controls.minDistance=3.5;controls.maxDistance=11;
    const render=()=>renderer.render(scene,camera);
    controls.addEventListener('change',render);
    let focusFrame=0;
    const cancelFocus=()=>{if(focusFrame){cancelAnimationFrame(focusFrame);focusFrame=0;}};
    controls.addEventListener('start',cancelFocus);
    scene.add(new THREE.HemisphereLight(0xffffff,0xb0c9d0,2.3));
    const key=new THREE.DirectionalLight(0xfff1ec,3);key.position.set(-3,4,5);scene.add(key);
    const fill=new THREE.DirectionalLight(0xe3f5ff,2);fill.position.set(4,1,-3);scene.add(fill);
    const group=new THREE.Group();scene.add(group);
    const meshes:THREE.Mesh[]=[];
    const resize=()=>{const w=element.clientWidth,h=element.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();render();};
    const observer=new ResizeObserver(resize);observer.observe(element);resize();
    const pointer=new THREE.Vector2();const raycaster=new THREE.Raycaster();let downX=0,downY=0;
    const down=(event:PointerEvent)=>{downX=event.clientX;downY=event.clientY;};
    const select=(event:PointerEvent)=>{
      if(Math.hypot(event.clientX-downX,event.clientY-downY)>5)return;
      const rect=renderer.domElement.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);
      raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects(meshes.filter(m=>m.userData.target),false)[0];
      if(hit)callback.current(hit.object.userData.target);
    };
    renderer.domElement.addEventListener('pointerdown',down);renderer.domElement.addEventListener('pointerup',select);
    const controller=new AbortController();
    async function load(){
      try{
        const response=await fetch('/anatomy/manifest.json',{signal:controller.signal});if(!response.ok)throw Error('Anatomy manifest unavailable');
        const manifest=await response.json();
        const objects=await Promise.all((manifest.meshes as Asset[]).map(async asset=>{
          const response=await fetch(`/anatomy/${asset.file}`,{signal:controller.signal});if(!response.ok)throw Error(`Unable to load ${asset.name}`);
          const object=new OBJLoader().parse(await response.text());
          object.traverse(child=>{if(child instanceof THREE.Mesh){
            child.geometry.computeVertexNormals();child.userData.target=asset.target;
            child.material=new THREE.MeshStandardMaterial({color:asset.target?0x648f9b:0xc58d8b,roughness:.65,metalness:0,side:THREE.DoubleSide});meshes.push(child);
          }});return object;
        }));
        if(disposed){meshes.forEach(mesh=>{mesh.geometry.dispose();(mesh.material as THREE.Material).dispose();});return;}
        objects.forEach(object=>group.add(object));
        // BodyParts3D uses anatomical Z-up; one shared transform preserves vessel alignment.
        group.rotation.x=-Math.PI/2;
        const box=new THREE.Box3().setFromObject(group);const center=box.getCenter(new THREE.Vector3());const size=box.getSize(new THREE.Vector3());
        const scale=3.2/Math.max(size.x,size.y,size.z);group.scale.setScalar(scale);group.position.copy(center.multiplyScalar(-scale));
        group.updateMatrixWorld(true);
        const boundsByTarget=new Map<Target,THREE.Box3>();
        for(const mesh of meshes){
          const t=mesh.userData.target as Target|undefined;
          if(!t)continue;
          mesh.geometry.computeBoundingBox();
          const bounds=mesh.geometry.boundingBox?.clone().applyMatrix4(mesh.matrixWorld);
          if(bounds){const existing=boundsByTarget.get(t);if(existing)existing.union(bounds);else boundsByTarget.set(t,bounds);}
        }
        const focusCenters=new Map<Target,THREE.Vector3>();
        focusCenters.set('CAD',new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3()));
        for(const [t,bounds] of boundsByTarget)focusCenters.set(t,bounds.getCenter(new THREE.Vector3()));
        const focus=(selected:Target)=>{
          const destination=focusCenters.get(selected);
          if(!destination)return;
          cancelFocus();
          const from=controls.target.clone();
          const start=performance.now();
          const duration=700;
          const animate=(now:number)=>{
            const progress=Math.min((now-start)/duration,1);
            const eased=progress*progress*(3-2*progress);
            controls.target.copy(from).lerp(destination,eased);
            controls.update();
            if(progress<1)focusFrame=requestAnimationFrame(animate);else focusFrame=0;
          };
          focusFrame=requestAnimationFrame(animate);
        };
        controls.saveState();sceneRef.current={meshes,controls,render,focus};setStatus('');render();
      }catch(e){if(!disposed){setStatus(e instanceof Error?e.message:'Unable to load anatomy');setFailed(true);}}
    }
    load();
    return ()=>{disposed=true;controller.abort();observer.disconnect();cancelFocus();controls.removeEventListener('start',cancelFocus);controls.dispose();renderer.domElement.removeEventListener('pointerdown',down);renderer.domElement.removeEventListener('pointerup',select);meshes.forEach(mesh=>{mesh.geometry.dispose();(mesh.material as THREE.Material).dispose();});renderer.dispose();renderer.domElement.remove();sceneRef.current=null;};
  },[]);
  useEffect(()=>{
    const current=sceneRef.current;if(!current)return;
    current.meshes.forEach(mesh=>{
      const t=mesh.userData.target as Target|undefined;const material=mesh.material as THREE.MeshStandardMaterial;
      if(t){const selected=target==='CAD'||t===target;material.color.set(arteryColors[t]);material.emissive.set(selected?arteryColors[t]:'#000000');material.emissiveIntensity=selected?(target==='CAD'?.12:.35):0;material.transparent=false;material.opacity=1;}
      else{material.transparent=transparent;material.opacity=transparent ? .22 : 1;material.depthWrite=!transparent;}
      material.needsUpdate=true;
    });current.render();
  },[target,results,transparent,status]);
  useEffect(()=>{sceneRef.current?.focus(target);},[target,status]);
  useEffect(()=>{sceneRef.current?.controls.reset();sceneRef.current?.render();},[resetKey]);
  return <><div className="three-mount" ref={mount} aria-label="Interactive BodyParts3D heart; drag to rotate and scroll to zoom" role="img"/>{status&&<div className={`viewer-loading ${failed?'viewer-error':''}`} role="status">{status}</div>}</>;
}
