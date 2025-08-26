// Import page JS - extracted from template to avoid inline conflicts
// eslint-disable-next-line

(function(){
  let fileId = null;

  async function previewSheets(){
    const fileInput = document.getElementById('fileInput');
    if (!fileInput || !fileInput.files.length) { alert('请先选择文件'); return; }
    const form = new FormData();
    form.append('file', fileInput.files[0]);
    const res = await fetch('/api/import/preview', { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) { alert(data.error || '预览失败'); return; }
    fileId = data.file_id;
    const sel = document.getElementById('sheetSelect');
    const wrap = document.getElementById('sheetSelectWrap');
    if (!sel) return;
    sel.innerHTML = '';
    (data.sheets || []).forEach(name => {
      const opt = document.createElement('option'); opt.value = name; opt.textContent = name;
      sel.appendChild(opt);
    });
    if (sel.options.length > 0){ sel.selectedIndex = 0; }
    if (wrap) wrap.style.display = 'block';
    await inspectSelectedSheet();
  }

  async function inspectSelectedSheet(){
    const sel = document.getElementById('sheetSelect');
    const box = document.getElementById('inspect');
    if (!sel || !box) return;
    const sheet = sel.value;
    box.style.display = 'none'; box.className='alert alert-info'; box.innerHTML='';
    if (!fileId || !sheet) return;
    const res = await fetch('/api/import/preview/inspect', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ file_id: fileId, sheet_name: sheet })
    });
    const data = await res.json();
    if (!res.ok) { box.style.display='block'; box.className='alert alert-danger'; box.textContent = data.error || '检查失败'; return; }
    const cols = (data.columns_normalized||[]).join('、') || '(空)';
    const subjects = (data.subjects_present||[]).join('、') || '(无)';
    const mode = data.mode;
    const sample = (data.sample_rows||[]).map((r,i)=> `${i+1}) ` + JSON.stringify(r)).join('<br/>');
    let html = `<div><strong>识别列：</strong>${cols}</div>` +
               `<div><strong>识别模式：</strong>${mode==='template'?'新模板':(mode==='legacy'?'旧模式':'未知')}</div>` +
               `<div><strong>检测到的学科列：</strong>${subjects}</div>` +
               (sample?`<div class="mt-2"><strong>样例(最多3行)：</strong><br/>${sample}</div>`:'');
    box.innerHTML = html; box.style.display='block';
    const ok = !!data.can_import;
    const importBtn = document.getElementById('importBtn');
    const importStuBtn = document.getElementById('importStudentsBtn');
    if (importBtn) importBtn.disabled = !ok;
    if (importStuBtn) importStuBtn.disabled = !ok;
  }

  async function importGrades(){
    const btn = document.getElementById('importBtn');
    if (btn){ btn.disabled = true; btn.textContent = '导入中...'; }
    try {
      const sheet = (document.getElementById('sheetSelect')||{}).value;
      if (!fileId || !sheet) { alert('请先预览并选择工作表'); return; }
      const examName = (document.getElementById('examNameInput')||{}).value?.trim() || 'default';
      const examType = (document.getElementById('examTypeSelect')||{}).value;
      const res = await fetch('/api/import/grades', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_id: fileId, sheet_name: sheet, exam_name: examName, exam_type: examType })
      });
      const data = await res.json();
      const result = document.getElementById('result');
      if (res.ok) {
        const skipped = data.skipped ? `；跳过空行 ${data.skipped} 条` : '';
        result.innerHTML = `<div class="alert alert-success">导入完成：新增 ${data.created} 条，更新 ${data.updated} 条${skipped}。</div>`;
      } else {
        let detailHtml = '';
        if (Array.isArray(data.details) && data.details.length) {
          const top = data.details.slice(0, 5).map(x=>`<li>${x}</li>`).join('');
          const more = data.details.length>5 ? `<div class=\"small text-muted\">其余 ${data.details.length-5} 条省略</div>` : '';
          detailHtml = `<ul class=\"mb-1\">${top}</ul>${more}`;
        }
        result.innerHTML = `<div class=\"alert alert-danger\">导入失败：${data.error || '未知错误'}${detailHtml?'<hr/>'+detailHtml:''}</div>`;
      }
    } catch(e){
      const result = document.getElementById('result');
      if (result) result.innerHTML = `<div class="alert alert-danger">导入失败：${(e && e.message) ? e.message : '异常'}</div>`;
    } finally {
      if (btn){ btn.disabled = false; btn.textContent = '开始导入'; }
      // 导入失败时，后端已删除上传文件，这里刷新一下列表，避免看到失败条目
      try{ loadUploadList(); }catch(e){}
    }
  }

  async function importStudents(){
    const sheet = (document.getElementById('sheetSelect')||{}).value;
    if (!fileId || !sheet) { alert('请先预览并选择工作表'); return; }
    const autoCreate = !!((document.getElementById('autoCreateUsers')||{}).checked);
    const defaultPwd = (document.getElementById('defaultPassword')||{}).value || '123456';
    const res = await fetch('/api/import/students', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id: fileId, sheet_name: sheet, auto_create_users: autoCreate, default_password: defaultPwd })
    });
    const data = await res.json();
    const result = document.getElementById('resultStudents');
    if (res.ok) {
      result.innerHTML = `<div class="alert alert-success">导入完成：新增学生 ${data.students_created} 条，更新 ${data.students_updated} 条；新增用户 ${data.users_created} 个。</div>`;
      loadUploadList();
    } else {
      result.innerHTML = `<div class="alert alert-danger">导入失败：${data.error || '未知错误'}</div>`;
    }
  }

  async function loadUploadList(){
    try {
      const res = await fetch('/api/import/files');
      const data = await res.json();
      const tb = document.querySelector('#uploadTable tbody');
      if (!tb) return;
      tb.innerHTML = '';
      (data.items||[]).forEach(it => {
        const tr = document.createElement('tr');
        const dt = new Date(it.mtime*1000);
        const examByFilename = (it.filename||'').replace(/\.[^.]+$/, '');
        tr.innerHTML = `<td><input type="checkbox" class="upload-cb" value="${it.file_id}"></td><td>${it.filename||it.file_id+'.xlsx'}</td><td>${it.file_id}</td><td>${it.exam_name||''}</td><td>${examByFilename||''}</td><td>${(it.size/1024).toFixed(1)} KB</td><td>${dt.toLocaleString()}</td>`;
        // 填充便于批量操作的元数据
        const ckb = tr.querySelector('input.upload-cb');
        if (ckb){ ckb.dataset.exam = it.exam_name||''; ckb.dataset.filename = it.filename||''; }
        const tdOp = document.createElement('td');
        const badge = document.createElement('span');
        const badgeExam = (it.exam_name||'') || ((it.filename||'').replace(/\.[^.]+$/, ''));
        badge.className = 'badge text-bg-warning me-2';
        badge.textContent = badgeExam ? `将删除：${badgeExam}` : '将删除：<未知>';
        tdOp.appendChild(badge);
        const delBtn = document.createElement('button'); delBtn.className='btn btn-sm btn-outline-danger'; delBtn.textContent='删除';
        delBtn.onclick = async ()=>{
          const exam = badgeExam;
          const msg = exam ? `确认删除该文件，并删除“${exam}”考试的所有成绩数据？此操作不可恢复！` : '确认删除该文件及其关联考试的所有数据？此操作不可恢复！';
          if (!confirm(msg)) return;
          const url = '/api/import/files/'+it.file_id + '?delete_grades=1';
          const r = await fetch(url, { method: 'DELETE' });
          const d = await r.json();
          if (r.ok) {
            if (d.grades_deleted) { alert('已删除关联成绩 '+ d.grades_deleted +' 条'); }
            loadUploadList();
          } else { alert(d.error||'删除失败'); }
        };
        tdOp.appendChild(delBtn); tr.appendChild(tdOp); tb.appendChild(tr);
      });
    } catch(e) { console.warn('load uploads failed', e); }
  }

  function toggleAllUploads(checked){
    document.querySelectorAll('#uploadTable .upload-cb').forEach(x=> x.checked = checked);
    updateSelectionSummary();
  }

  function updateSelectionSummary(){
    const cbs = Array.from(document.querySelectorAll('#uploadTable .upload-cb:checked'));
    const ids = cbs.map(x=>x.value);
    const exams = cbs.map(x=> x.dataset.exam || (x.dataset.filename||'').replace(/\.[^.]+$/, '')).filter(Boolean);
    const uniqExams = Array.from(new Set(exams));
    const el = document.getElementById('selectionSummary');
    if (!el) return;
    if (!ids.length){ el.textContent = ''; return; }
    el.innerHTML = `已选 ${ids.length} 个文件；将删除考试：` + (uniqExams.length? uniqExams.map(e=>`<span class="badge text-bg-secondary me-1">${e}</span>`).join('') : '<span class="text-muted">(未知)</span>');
  }

  async function batchDeleteSelected(){
    const cbs = Array.from(document.querySelectorAll('#uploadTable .upload-cb:checked'));
    const ids = cbs.map(x=>x.value);
    if (!ids.length){ alert('请选择文件'); return; }
    const exams = cbs.map(x=> x.dataset.exam || (x.dataset.filename||'').replace(/\.[^.]+$/, '')).filter(Boolean);
    const uniqExams = Array.from(new Set(exams));
    const extra = uniqExams.length ? `\n将删除以下考试：\n- ${uniqExams.join('\n- ')}` : '';
    if (!confirm(`确认删除选中的 ${ids.length} 个文件及其关联考试的所有数据？此操作不可恢复！${extra}`)) return;
    const r = await fetch('/api/import/files/batch-delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ file_ids: ids, delete_grades: true }) });
    const d = await r.json();
    if (r.ok){ if (d.grades_deleted) alert('已删除关联成绩 '+ d.grades_deleted +' 条'); loadUploadList(); }
    else { alert(d.error||'批量删除失败'); }
  }

  function bindEvents(){
    const b1 = document.getElementById('previewBtn'); if (b1) b1.addEventListener('click', previewSheets);
    const b1b = document.getElementById('previewBtn2'); if (b1b) b1b.addEventListener('click', previewSheets);
    const imp = document.getElementById('importBtn'); if (imp) imp.addEventListener('click', importGrades);
    const impStu = document.getElementById('importStudentsBtn'); if (impStu) impStu.addEventListener('click', importStudents);
    const sel = document.getElementById('sheetSelect'); if (sel) sel.addEventListener('change', inspectSelectedSheet);
    const ref = document.getElementById('uploadRefreshBtn'); if (ref) ref.addEventListener('click', ()=>{ loadUploadList(); updateSelectionSummary(); });
    const delBatch = document.getElementById('batchDeleteBtn'); if (delBatch) delBatch.addEventListener('click', batchDeleteSelected);
    const tog = document.getElementById('toggleAllUploads'); if (tog) tog.addEventListener('change', (e)=> toggleAllUploads(e.target.checked));
    document.addEventListener('change', (e)=>{ if (e.target && e.target.classList.contains('upload-cb')) updateSelectionSummary(); });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    // Optional initial load
    loadUploadList();
  });
})();

