'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const M=require('../web/products-model.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/products.json'),'utf8'));
const empty={insurer:'',category:'',pay:'',query:'',previous:false,compare:[]};

test('payment filters keep years, ages and continuous payments distinct',()=>{
 assert.equal(M.payKey(10),'years:10');assert.equal(M.payKey('10년납(예시)'),'years:10');
 assert.equal(M.payKey('90세납'),'age:90');assert.equal(M.payKey('전기납'),'full');
 const ten=M.filterProducts(data,{...empty,pay:'years:10'});
 assert(ten.some(p=>p.id==='SH02'));assert(!ten.some(p=>p.id==='ME04'));
 assert(!M.payOptions(data).some(p=>p.value==='years:90'));
});
test('combined insurer, type and payment filters work without mutating catalog',()=>{
 const result=M.filterProducts(data,{...empty,insurer:'푸본현대생명',category:'종신',pay:'years:20'});
 assert.deepEqual(result.map(p=>p.id),['F01']);assert.equal(data.products.length,60);
 assert.equal(M.filterProducts(data,{...empty,insurer:'흥국생명'}).length,0);
});
test('prior documents are hidden unless explicitly requested',()=>{
 const fubon=data.products.find(p=>p.id==='F01'),met=data.products.find(p=>p.id==='ME02');
 assert.equal(M.visibleExamples(fubon,empty).length,0);
 assert.equal(M.visibleExamples(fubon,{...empty,previous:true}).length,1);
 assert.equal(M.visibleExamples(met,empty).length,3);
 assert.equal(M.visibleExamples(met,{...empty,pay:'years:7'}).length,0);
});
test('missing numeric values never become zero percent',()=>{
 assert.equal(M.formatRate(null),'미확인');assert.equal(M.formatRate(''),'미확인');
 assert.equal(M.formatRate(0),'0.0%');assert.equal(M.formatRate(1.2378),'123.78%');
});
test('bookmarked filters round-trip and cannot include pending product IDs',()=>{
 const state={...empty,insurer:'메트라이프생명',category:'연금',pay:'years:10',query:'달러',previous:true,compare:['ME02','F02']};
 const url=M.writeState('https://example.com/?date=2026-11-19&period=2026-11#archive',state);
 assert.equal(url.searchParams.get('view'),'products');assert(!url.searchParams.has('date'));assert(!url.hash);
 assert.deepEqual(M.readState(url.searchParams,data),state);
 const clean=M.readState(new URLSearchParams('insurer=unknown&category=unknown&pay=years:999&compare=HK01,ME02,ME02,ME03,F01,F02'),data);
 assert.equal(clean.insurer,'');assert.equal(clean.pay,'');assert.deepEqual(clean.compare,['ME02','ME03','F01']);
});
test('external sources reject executable URLs and embedded credentials',()=>{
 assert.equal(M.safeURL('javascript:alert(1)'),null);assert.equal(M.safeURL('https://user:pw@example.com/'),null);
 assert.equal(M.safeURL('https://example.com/source'),'https://example.com/source');
});
