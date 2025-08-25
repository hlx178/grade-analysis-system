// Import page JS - extracted from template to avoid inline conflicts
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
        tr.innerHTML = `<td><input type="checkbox" class="upload-cb" value="${it.file_id}"></td><td>${it.filename||it.file_id+'.xlsx'}</td><td>${it.file_id}</td><td>${it.exam_name||''}</td><td>${(it.size/1024).toFixed(1)} KB</td><td>${dt.toLocaleString()}</td>`;
        const tdOp = document.createElement('td');
        const delBtn = document.createElement('button'); delBtn.className='btn btn-sm btn-outline-danger'; delBtn.textContent='删除';
        delBtn.onclick = async ()=>{
          if (!confirm('确认删除该文件？')) return;
          const withGrades = confirm('是否同时删除该文件对应考试名称下的所有成绩记录？[确定=是/取消=否]');
          let url = '/api/import/files/'+it.file_id + (withGrades? '?delete_grades=1' : '');
          if (withGrades && !it.exam_name){
            const useDefault = confirm('元数据缺少考试名称，是否使用 "default" 作为回退进行清理？');
            if (useDefault) url += '&fallback_by=default';
          }
          const r = await fetch(url, { method: 'DELETE' });
          const d = await r.json();
          if (r.ok) {
            if (d.grades_deleted) { alert('已删除关联成绩 '+ d.grades_deleted +' 条'); }
            else if (withGrades) { alert('未发现可删除的关联成绩，请尝试使用“按考试名称清理成绩”工具'); }
            loadUploadList();
          }
          else { alert(d.error||'删除失败'); }
        };
        tdOp.appendChild(delBtn); tr.appendChild(tdOp); tb.appendChild(tr);
      });
    } catch(e) { console.warn('load uploads failed', e); }
  }

  function toggleAllUploads(checked){
    document.querySelectorAll('#uploadTable .upload-cb').forEach(x=> x.checked = checked);
  }

  async function batchDeleteSelected(){
    const ids = Array.from(document.querySelectorAll('#uploadTable .upload-cb:checked')).map(x=>x.value);
    if (!ids.length){ alert('请选择文件'); return; }
    if (!confirm('确认删除选中的 ' + ids.length + ' 个文件？')) return;
    const withGrades = confirm('是否同时删除这些文件对应考试名称下的成绩记录？[确定=是/取消=否]');
    const r = await fetch('/api/import/files/batch-delete', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ file_ids: ids, delete_grades: withGrades }) });
    const d = await r.json();
    if (r.ok){ if (d.grades_deleted) alert('已删除关联成绩 '+ d.grades_deleted +' 条'); loadUploadList(); }
    else { alert(d.error||'批量删除失败'); }
  }

  async function cleanupByExam(){
    const exam = (document.getElementById('cleanupExam')||{}).value?.trim();
    const subj = (document.getElementById('cleanupSubject')||{}).value?.trim();
    if (!exam){ alert('请输入考试名称'); return; }
    const res = await fetch('/api/grades/cleanup-by-exam', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ exam_name: exam, subject_code: subj||undefined }) });
    const data = await res.json();
    const box = document.getElementById('cleanupResult');
    if (res.ok){ box.textContent = `已删除 ${data.deleted||0} 条成绩`; }
    else { box.textContent = `清理失败：${data.error||res.status}`; }
  }

  async function cleanupAllGrades(){
    if (!confirm('将要删除所有成绩（或指定学科的所有成绩），不可恢复。确认继续？')) return;
    const subj = (document.getElementById('cleanupAllSubject')||{}).value?.trim();
    const res = await fetch('/api/grades/cleanup-all', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ confirm: true, subject_code: subj||undefined }) });
    const data = await res.json();
    const box = document.getElementById('cleanupAllResult');
    if (res.ok){ box.textContent = `已删除 ${data.deleted||0} 条成绩`; }
    else { box.textContent = `清理失败：${data.error||res.status}`; }
  }

  async function cleanupNameless(cascade){
    if (cascade && !confirm('将删除“姓名为空”的学生及其所有成绩，确认继续？')) return;
    const res = await fetch('/api/admin/cleanup/nameless-students', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ cascade }) });
    const data = await res.json();
    const box = document.getElementById('cleanupNamelessResult');
    if (res.ok){ box.textContent = `已删除学生 ${data.deleted_students||0} 个`; }
    else { box.textContent = `清理失败：${data.error||res.status}`; }
  }

  function bindEvents(){
    const b1 = document.getElementById('previewBtn'); if (b1) b1.addEventListener('click', previewSheets);
    const b1b = document.getElementById('previewBtn2'); if (b1b) b1b.addEventListener('click', previewSheets);
    const imp = document.getElementById('importBtn'); if (imp) imp.addEventListener('click', importGrades);
    const impStu = document.getElementById('importStudentsBtn'); if (impStu) impStu.addEventListener('click', importStudents);
    const sel = document.getElementById('sheetSelect'); if (sel) sel.addEventListener('change', inspectSelectedSheet);
    const ref = document.getElementById('uploadRefreshBtn'); if (ref) ref.addEventListener('click', loadUploadList);
    const delBatch = document.getElementById('batchDeleteBtn'); if (delBatch) delBatch.addEventListener('click', batchDeleteSelected);
    const tog = document.getElementById('toggleAllUploads'); if (tog) tog.addEventListener('change', (e)=> toggleAllUploads(e.target.checked));
    const cbExam = document.getElementById('cleanupByExamBtn'); if (cbExam) cbExam.addEventListener('click', cleanupByExam);
    const cbAll = document.getElementById('cleanupAllBtn'); if (cbAll) cbAll.addEventListener('click', cleanupAllGrades);
    const nameless = document.getElementById('cleanupNamelessBtn'); if (nameless) nameless.addEventListener('click', ()=> cleanupNameless(false));
    const nameless2 = document.getElementById('cleanupNamelessCascadeBtn'); if (nameless2) nameless2.addEventListener('click', ()=> cleanupNameless(true));
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    // Optional initial load
    loadUploadList();
  });
})();

