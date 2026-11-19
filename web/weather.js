'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const endpoint='https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul&forecast_days=1';
  const seoul=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'});
  let cached=window.BRIEFING_BOOTSTRAP?.weather;
  function condition(code,isDay) {
    if(code===0)return [isDay?'☀':'☾','맑음'];
    if(code===1)return [isDay?'🌤':'☾','대체로 맑음'];
    if(code===2)return ['⛅','구름 조금'];
    if(code===3)return ['☁','흐림'];
    if([45,48].includes(code))return ['🌫','안개'];
    if([51,53,55,56,57].includes(code))return ['🌧','이슬비'];
    if([61,63,65,66,67,80,81,82].includes(code))return ['🌧','비'];
    if([71,73,75,77,85,86].includes(code))return ['🌨','눈'];
    if([95,96,99].includes(code))return ['⛈','뇌우'];
    return ['—','상태 확인 불가'];
  }
  function valid(value) {
    return value?.date===seoul.format(new Date()) && [value.minimum,value.maximum,value.temperature].every(Number.isFinite) && value.minimum<=value.maximum && Number.isFinite(Date.parse(value.weather_time));
  }
  function render(value) {
    $('weather-location').textContent='서울 오늘 · '+seoul.format(new Date()).slice(5).replace('-','/');
    if(!valid(value)) {
      $('weather-icon').textContent='—';$('weather-condition').textContent='날씨 확인 불가';
      $('weather-temperatures').hidden=true;$('weather-updated').textContent='오늘 예보를 다시 확인 중입니다.';return;
    }
    const [icon,label]=condition(value.weather_code,value.is_day);
    $('weather-icon').textContent=icon;
    $('weather-condition').textContent=label+' · '+value.temperature.toFixed(1)+'°';
    $('weather-low').textContent=value.minimum.toFixed(1)+'°';
    $('weather-high').textContent=value.maximum.toFixed(1)+'°';
    $('weather-temperatures').hidden=false;
    const time=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value.weather_time));
    $('weather-updated').textContent=time+' 기준 모델·오늘 예보';
  }
  async function refresh() {
    render(cached);
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),12000);
    try {
      const response=await fetch(endpoint,{signal:controller.signal});
      if(!response.ok)throw new Error('Weather unavailable');
      const raw=await response.json();
      const value={date:raw.daily.time[0],weather_time:raw.current.time+'+09:00',temperature:raw.current.temperature_2m,weather_code:raw.current.weather_code,is_day:!!raw.current.is_day,minimum:raw.daily.temperature_2m_min[0],maximum:raw.daily.temperature_2m_max[0]};
      if(!valid(value))throw new Error('Weather date mismatch');
      cached=value;render(cached);
    } catch { render(cached); }
    finally {clearTimeout(timer);}
  }
  refresh();setInterval(refresh,30*60*1000);
})();
