'use client';
import {useEffect, useRef, useState} from 'react';
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {OBJLoader} from 'three/addons/loaders/OBJLoader.js';
import {Results, Target} from '@/lib/types';

type Asset={file:string;name:string;target:Target|null};
export default function HeartViewer({target,results,resetKey,transparent,onSelect}:{target:Target;results:Results|null;resetKey:number;transparent:boolean;onSelect:(t:Target)=>void}){
  const mount=useRef<HTMLDivElement>(null);
  const sceneRef=useRef<{meshes:THREE.Mesh[];controls:OrbitControls;render:()=>void}|null>(null);
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
        controls.saveState();sceneRef.current={meshes,controls,render};setStatus('');render();
      }catch(e){if(!disposed){setStatus(e instanceof Error?e.message:'Unable to load anatomy');setFailed(true);}}
    }
    load();
    return ()=>{disposed=true;controller.abort();observer.disconnect();controls.dispose();renderer.domElement.removeEventListener('pointerdown',down);renderer.domElement.removeEventListener('pointerup',select);meshes.forEach(mesh=>{mesh.geometry.dispose();(mesh.material as THREE.Material).dispose();});renderer.dispose();renderer.domElement.remove();sceneRef.current=null;};
  },[]);
  useEffect(()=>{
    const current=sceneRef.current;if(!current)return;
    current.meshes.forEach(mesh=>{
      const t=mesh.userData.target as Target|undefined;const material=mesh.material as THREE.MeshStandardMaterial;
      if(t){const p=results?.predictions[t]?.probability;material.color.set(p===undefined?'#548392':new THREE.Color('#2a9b97').lerp(new THREE.Color('#d35351'),p));material.emissive.set(t===target?'#502723':'#000000');material.emissiveIntensity=t===target ? .2 : 0;material.transparent=false;material.opacity=1;}
      else{material.transparent=transparent;material.opacity=transparent ? .22 : 1;material.depthWrite=!transparent;}
      material.needsUpdate=true;
    });current.render();
  },[target,results,transparent,status]);
  useEffect(()=>{sceneRef.current?.controls.reset();sceneRef.current?.render();},[resetKey]);
  return <><div className="three-mount" ref={mount} aria-label="Interactive BodyParts3D heart; drag to rotate and scroll to zoom" role="img"/>{status&&<div className={`viewer-loading ${failed?'viewer-error':''}`} role="status">{status}</div>}</>;
}
