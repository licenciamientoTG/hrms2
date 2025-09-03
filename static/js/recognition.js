(function(){
  const colorPicker  = document.getElementById('colorPicker');
  const colorSwatch  = document.getElementById('colorSwatch');
  const colorHexLbl  = document.getElementById('colorHexLabel');
  const coverPreview = document.getElementById('coverPreview');
  const coverImage   = document.getElementById('coverImage');
  const coverInput   = document.getElementById('coverInput');
  const pointsSwitch = document.getElementById('pointsSwitch');
  const pointsBadge  = document.getElementById('pointsBadge');
  const pointsValue  = document.getElementById('pointsValue');
  const pointsInput  = document.querySelector('input[name="points"]');
  const confettiSwitch = document.getElementById('confettiSwitch');

  function applyColor(){
    const hex = (colorPicker?.value || '#1E3361').toUpperCase();
    colorSwatch.style.background = hex;
    colorHexLbl.textContent = hex;
    coverPreview.style.background = hex;
  }
  function applyPoints(){
    const on = pointsSwitch?.checked;
    pointsBadge.style.display = on ? 'inline-block' : 'none';
    pointsValue.textContent = pointsInput?.value || '0';
  }
  function toggleConfetti(){
    if(!confettiSwitch?.checked && !coverInput?.value){
      coverImage.style.display = "none";
    } else {
      coverImage.style.display = "block";
    }
  }
  colorPicker?.addEventListener('input', applyColor);
  pointsSwitch?.addEventListener('change', applyPoints);
  pointsInput?.addEventListener('input', applyPoints);
  confettiSwitch?.addEventListener('change', toggleConfetti);
  coverInput?.addEventListener('change', (e)=>{
    const file = e.target.files?.[0];
    if(!file) return;
    const reader = new FileReader();
    reader.onload = (ev)=>{ coverImage.src = ev.target.result; coverImage.style.display="block"; };
    reader.readAsDataURL(file);
  });

  applyColor(); applyPoints(); toggleConfetti();
})();
