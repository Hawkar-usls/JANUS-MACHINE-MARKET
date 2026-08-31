(() => {
  'use strict';
  async function install() {
    try {
      const manifest = await fetch('MACHINE_INGRESS.json', {cache:'no-store'}).then(r => r.json());
      window.JANUS_MACHINE_INGRESS = manifest;
      const grid = document.querySelector('#surfaceGrid');
      if (grid && !grid.querySelector('a[href="MACHINE_INGRESS.json"]')) {
        const a = document.createElement('a');
        a.className = 'surface';
        a.href = 'MACHINE_INGRESS.json';
        a.innerHTML = '<b>MACHINE_INGRESS.json</b><small>Direct authenticated machine task ingress · no HTML required</small>';
        grid.prepend(a);
      }
      const truthbar = document.querySelector('#truthbar');
      if (truthbar && !truthbar.querySelector('.truth.machine-ingress')) {
        const chip = document.createElement('span');
        chip.className = 'truth live machine-ingress';
        chip.innerHTML = 'MACHINE INGRESS <b>API LIVE</b>';
        truthbar.insertBefore(chip, truthbar.children[2] || null);
      }
    } catch (err) {
      console.error('JANUS machine ingress manifest unavailable', err);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
