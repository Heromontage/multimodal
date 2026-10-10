import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',timeout:60000,workers:1,use:{baseURL:process.env.APP_URL||'http://127.0.0.1:3001',headless:true,launchOptions:{args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']}},reporter:'list'});
