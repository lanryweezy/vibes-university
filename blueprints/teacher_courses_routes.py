@teacher_courses_bp.route('/lessons/<int:lesson_id>/delete', methods=['POST'])
@require_teacher_auth
@csrf_protect
def delete_lesson(lesson_id):
    """Delete a lesson."""
    conn = None
    try:
        conn = get_db_connection()
        # Check if lesson exists
        lesson = conn.execute("SELECT course_id FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        if not lesson:
            return "Lesson not found", 404
        
        course_id = lesson['course_id']
        
        # Delete lesson
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        conn.commit()
        log_info(app_logger, "Lesson deleted successfully", lesson_id=lesson_id)
        
        return redirect(url_for('teacher_courses_bp.manage_course_content', course_id=course_id))
    except Exception as e:
        if conn:
            return_db_connection(conn)
        log_error(db_logger, "Failed to delete lesson", error=str(e))
        return "Error deleting lesson", 500
    finally:
        if conn:
            return_db_connection(conn)


@teacher_courses_bp.route('/course-studio')
@require_teacher_auth
def teacher_course_studio_page():
    """Teacher course design studio - same interface as admin but with teacher permissions."""
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vibes University - Course Design Studio</title>
        <link rel="stylesheet" href="https://unpkg.com/easymde/dist/easymde.min.css">
        <script src="https://unpkg.com/easymde/dist/easymde.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #1a1a2e; color: white; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
            .header-bar { background: rgba(255,255,255,0.1); padding: 1rem 2rem; color: #4CAF50; border-bottom: 1px solid #4CAF50;}
            .studio-container { display: grid; grid-template-columns: 280px 1fr 320px; flex-grow: 1; gap: 1rem; padding: 1rem; overflow: hidden; }
            .panel { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 1.5rem; border: 1px solid rgba(76,175,80,0.2); overflow-y: auto; }
            .panel-title { color: #4CAF50; font-size: 1.2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(76,175,80,0.3); }
            .main-canvas-area { display: flex; flex-direction: column; }
            .tabs { display: flex; margin-bottom: 1rem; border-bottom: 1px solid rgba(76,175,80,0.3); }
            .tab { padding: 0.8rem 1rem; background: none; border: none; color: #ccc; cursor: pointer; border-bottom: 2px solid transparent; }
            .tab.active { color: #4CAF50; border-bottom-color: #4CAF50; }
            .tab-content { display: none; flex-grow: 1; overflow-y: auto; }
            .tab-content.active { display: block; }
            .course-canvas { min-height: 400px; background: rgba(0,0,0,0.1); border: 2px dashed rgba(76,175,80,0.3); border-radius: 8px; padding: 1rem; position: relative; }
            .lesson-drop-indicator { height: 2px; background-color: #4CAF50; margin: 2px 0; width: 100%; }
            .module-drop-indicator { height:10px; background:rgba(76,175,80,0.5); margin: 5px 0; border-radius: 3px;}
            .drop-target-highlight { background-color: rgba(76,175,80,0.1); }
            .dragging-item { box-shadow: 0 0 15px rgba(76, 175, 80, 0.7); border-color: rgba(76, 175, 80, 0.7) !important; }

            button, input, select, textarea { background-color: rgba(255,255,255,0.1); border: 1px solid rgba(76,175,80,0.3); color: white; padding: 0.5em; border-radius: 5px; margin-bottom: 0.5em; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
            button { cursor: pointer; background-color: #4CAF50; }
            .element-btn { display: block; width: 100%; margin-bottom: 0.5rem; background: linear-gradient(45deg, #4CAF50, #8BC34A); }
            .form-group { margin-bottom: 1rem; }
            .form-group label { display: block; color: #81C784; margin-bottom: .3rem; font-size:0.9em; }
            .btn-primary { background: linear-gradient(45deg, #4CAF50, #8BC34A); color: white; padding: 0.8rem 1.5rem; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 1rem; transition: all 0.3s; }
            .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(76, 175, 80, 0.3); }
            .btn-secondary { background: #555; }
            .btn-danger { background: #d9534f; }
            .EasyMDEContainer .CodeMirror { background: rgba(255,255,255,0.05); border-color: rgba(76,175,80,0.3); color:white; }
            .editor-toolbar a { color: #ccc !important; }
            .editor-toolbar a.active, .editor-toolbar a:hover { background: rgba(76,175,80,0.3) !important; border-color: #4CAF50 !important; }
            .CodeMirror-cursor { border-left: 1px solid white !important; }
            #course-preview-canvas .module-preview-item { margin-top:20px; padding:15px; background:rgba(255,255,255,0.03); border-radius:5px; border-left: 3px solid #81C784; }
            #course-preview-canvas .module-preview-item h3 { color:#81C784; margin-bottom:10px; font-size:1.4em;}
            #course-preview-canvas .lesson-preview-item { margin-bottom:15px; padding:10px; background:rgba(255,255,255,0.04); border-radius:5px; }
            #course-preview-canvas .lesson-preview-item h4 { color:#e0e0e0; font-size:1.1em; margin-bottom:8px;}
            #course-preview-canvas .quiz-option { padding:8px; margin:5px 0; border:1px solid #555; border-radius:4px; }
            #course-preview-canvas .download-btn { opacity:0.7; cursor:not-allowed; padding:8px 12px; background:#555; border:none; color:#ccc; }
            #course-preview-canvas .video-container-preview iframe, #course-preview-canvas .video-container-preview video {max-width:100%; border-radius:5px;}
            #course-preview-canvas .markdown-content img {max-width:100%; height:auto; border-radius:5px; margin:10px 0;}
        </style>
    </head>
    <body>
        <div class="header-bar"><h1>🎓 Course Design Studio</h1></div>
        <div class="studio-container">
            <div class="panel" id="left-panel">
                <div class="panel-title">📚 Courses</div>
                <div id="course-list-section"><button id="new-course-btn">New Course</button><ul id="course-list" style="list-style:none; padding-left:0;"></ul></div>
                <hr style="margin: 1rem 0; border-color: rgba(76,175,80,0.2);">
                <div class="panel-title">📦 Modules</div>
                <div id="module-management-section"><button id="add-new-module-btn" style="width:100%; margin-bottom:10px;">Add New Module</button></div>
                <hr style="margin: 1rem 0; border-color: rgba(76,175,80,0.2);">
                <div class="panel-title">➕ Add Element</div>
                <div id="element-palette">
                    <button class="element-btn" data-type="text">📝 Text Content</button>
                    <button class="element-btn" data-type="video">🎥 Video Lesson</button>
                    <button class="element-btn" data-type="quiz">❓ Interactive Quiz</button>
                    <button class="element-btn" data-type="download">📁 Downloadable Resource</button>
                </div>
                <hr style="margin: 1rem 0; border-color: rgba(76,175,80,0.2);">
                <div class="panel-title">🚀 Templates</div>
                <div id="template-palette">
                    <button class="element-btn template-btn" data-template-name="marketing-module">📈 Marketing Module</button>
                    <button class="element-btn template-btn" data-template-name="coding-module">💻 Coding Module</button>
                    <button class="element-btn template-btn" data-template-name="income-module">💰 Income Generation</button>
                </div>
            </div>
            <div class="panel main-canvas-area" id="center-panel">
                <div class="tabs">
                    <button class="tab active" data-tab="design">🎨 Design</button>
                    <button class="tab" data-tab="preview">👁️ Preview</button>
                    <button class="tab" data-tab="settings">⚙️ Settings</button>
                </div>
                <div id="design-tab" class="tab-content active">
                    <div class="panel-title" id="current-course-title">Select or Create a Course</div>
                    <div class="course-canvas" id="course-canvas-main"><p style="text-align:center; color:#777; margin-top:50px;">Select a course to start designing, or create a new one.</p></div>
                </div>
                <div id="preview-tab" class="tab-content">
                    <div class="panel-title">Course Preview</div>
                    <div class="course-canvas" id="course-preview-canvas"><p style="text-align:center; color:#777; margin-top:50px;">Select a course and switch to this tab to see its preview.</p></div>
                </div>
                <div id="settings-tab" class="tab-content">
                    <div class="panel-title">Course Settings</div>
                    <form id="course-settings-form">
                        <div class="form-group"><label for="setting-course-title">Course Title:</label><input type="text" id="setting-course-title" name="name" style="width:95%;"></div>
                        <div class="form-group"><label for="setting-course-description">Description:</label><textarea id="setting-course-description" name="description" rows="4" style="width:95%;"></textarea></div>
                        <div class="form-group"><label for="setting-course-difficulty">Difficulty:</label><select id="setting-course-difficulty" name="difficulty" style="width:95%;"><option value="Beginner">Beginner</option><option value="Intermediate" selected>Intermediate</option><option value="Advanced">Advanced</option></select></div>
                        <div class="form-group"><label for="setting-course-duration">Estimated Duration (e.g., 8 weeks):</label><input type="text" id="setting-course-duration" name="duration" style="width:95%;"></div>
                        <div class="form-group"><label for="setting-course-income">Income Potential (e.g., ₦500K-₦2M):</label><input type="text" id="setting-course-income" name="income_potential" style="width:95%;"></div>
                        <button type="button" id="save-course-settings-btn" class="btn-primary">Save Settings</button>
                    </form>
                </div>
            </div>
            <div class="panel" id="right-panel">
                <div class="panel-title">⚙️ Element Properties</div>
                <div id="properties-editor"><p style="text-align:center; color:#777; margin-top:30px;">Select a lesson element on the canvas to edit its properties.</p></div>
            </div>
        </div>
        <script>
            // --- Basic Modal Structure & Control ---
            const modalContainer = document.createElement('div');
            modalContainer.id = 'form-modal-container';
            Object.assign(modalContainer.style, { display: 'none', position: 'fixed', left: '0', top: '0', width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', zIndex: '1000', justifyContent: 'center', alignItems: 'center', padding: '20px' });
            modalContainer.innerHTML = `<div id="modal-content-box" style="background: #2c2c3e;padding:25px;border-radius:10px;min-width:300px;max-width:600px;box-shadow:0 5px 25px rgba(0,0,0,0.3);display:flex;flex-direction:column;max-height:90vh;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-shrink:0;"><h3 id="modal-title" style="color:#4CAF50;margin:0;">Modal Title</h3><button id="modal-close-btn" style="background:transparent;border:none;color:white;font-size:1.8rem;cursor:pointer;line-height:1;">&times;</button></div><div id="modal-form-content" style="overflow-y:auto;"></div></div>`;
            document.body.appendChild(modalContainer);
            const modalFormContentEl = document.getElementById('modal-form-content');
            const modalTitleEl = document.getElementById('modal-title');
            document.getElementById('modal-close-btn').onclick = () => closeModal();
            modalContainer.addEventListener('click', function(event) { if (event.target === modalContainer) closeModal(); });
            let currentSubmitCallback = null;
            function openModal(title, formHTML, submitCallback) {
                modalTitleEl.textContent = title;
                modalFormContentEl.innerHTML = formHTML;
                currentSubmitCallback = submitCallback;
                const formInModal = modalFormContentEl.querySelector('form');
                if (formInModal) { formInModal.onsubmit = async (e) => { e.preventDefault(); if(currentSubmitCallback) await currentSubmitCallback(new FormData(formInModal), closeModal); }; }
                modalContainer.style.display = 'flex';
            }
            function closeModal() { modalContainer.style.display = 'none'; modalFormContentEl.innerHTML = ''; currentSubmitCallback = null; }
            // --- End Basic Modal Structure & Control ---

            // --- Template Data ---
            const courseTemplates = {
                "marketing-module": [ { type: 'video', title: 'Intro to AI Marketing', props: { url: '', duration: '10 mins'} }, { type: 'text', title: 'Key Marketing Concepts with AI', props: { markdown_content: '# Key Concepts\\n\\n- AI Persona Generation\\n- Predictive Analytics\\n- Automated Content Creation'} }, { type: 'quiz', title: 'Marketing Basics Quiz', props: { question: 'What is ROI?', options: ['Return on Investment', 'Rate of Inflation', 'Risk of Incarceration'], correct_answer_index: 0 } } ],
                "coding-module": [ { type: 'text', title: 'Setting Up Your Dev Environment', props: { markdown_content: '# Setup Guide\\n\\n1. Install Python\\n2. Install VS Code\\n3. Get API Keys'} }, { type: 'video', title: 'Your First AI "Hello World"', props: { url: '', duration: '15 mins'} } ],
                "income-module": [ { type: 'video', title: 'Monetization Strategies with AI', props: {url: '', duration: '20 mins'} }, { type: 'download', title: 'AI Income Cheatsheet', props: {} }, { type: 'text', title: 'Case Study: AI Freelancing Success', props: { markdown_content: '# Case Study\\n\\nLearn how John Doe makes ₦1M monthly...'}} ]
            };
            // --- End Template Data ---

            function displaySelectedFileName(inputElement, displayElementId) {
                const displayElement = document.getElementById(displayElementId);
                if (displayElement) {
                    if (inputElement.files && inputElement.files.length > 0) {
                        displayElement.textContent = `Selected: ${inputElement.files[0].name}`;
                    } else {
                        displayElement.textContent = '';
                    }
                }
            }

            document.querySelectorAll('.tab').forEach(tab => {
                tab.addEventListener('click', function() {
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

                    this.classList.add('active');
                    const activeTabContent = document.getElementById(this.dataset.tab + '-tab');
                    activeTabContent.classList.add('active');

                    if (this.dataset.tab === 'settings' && currentCourseData) {
                        populateCourseSettingsForm(currentCourseData);
                    } else if (this.dataset.tab === 'preview') {
                        const previewCanvas = activeTabContent.querySelector('.course-canvas') || activeTabContent;
                        if (currentCourseData) {
                            renderCoursePreview(currentCourseData, previewCanvas);
                        } else {
                            previewCanvas.innerHTML = '<p style="padding:20px; text-align:center;">Please select a course to preview.</p>';
                        }
                    }
                });
            });

            function renderCoursePreview(courseData, previewAreaElement) {
                previewAreaElement.innerHTML = '';
                let previewHTML = `<div style="padding:10px; font-size:0.9em; line-height:1.6;">`;
                previewHTML += `<div style="border-bottom: 2px solid #4CAF50; margin-bottom:20px; padding-bottom:15px;">`;
                previewHTML += `<h1 style="color:#4CAF50; text-align:left; margin-bottom:5px; font-size:1.8em;">${courseData.name || 'Course Title'}</h1>`;
                previewHTML += `<p style="color:#ccc; margin-bottom:10px; font-size:0.95em;">${courseData.description || 'No course description.'}</p>`;
                if(courseData.course_settings) {
                    previewHTML += `<p style="font-size:0.8em; color:#aaa;">`;
                    if(courseData.course_settings.difficulty) previewHTML += `Difficulty: ${courseData.course_settings.difficulty} | `;
                    if(courseData.course_settings.duration) previewHTML += `Est. Duration: ${courseData.course_settings.duration}`;
                    if(courseData.course_settings.income_potential) previewHTML += ` | Income: ${courseData.course_settings.income_potential}`;
                    previewHTML += `</p>`;
                }
                previewHTML += `</div>`;

                if (courseData.modules && courseData.modules.length > 0) {
                    const sortedModules = [...courseData.modules].sort((a,b) => a.order_index - b.order_index);
                    sortedModules.forEach(module => {
                        previewHTML += `<div class="module-preview-item"><h3>${module.name}</h3>`;
                        const lessonsInModule = (courseData.lessons || []).filter(l => l.module_id === module.id).sort((a,b) => a.order_index - b.order_index);
                        if (lessonsInModule.length > 0) {
                            previewHTML += '<ul style="list-style:none; padding-left:0;">';
                            lessonsInModule.forEach(lesson => {
                                previewHTML += `<li class="lesson-preview-item"><h4>${lesson.lesson} <span style="font-size:0.8em; color:#aaa;">(${lesson.content_type})</span></h4>`;
                                const props = lesson.element_properties || {};
                                switch(lesson.content_type) {
                                    case 'text': case 'markdown':
                                        const mdContent = props.markdown_content || lesson.description || '';
                                        try { previewHTML += marked.parse(mdContent || ''); } catch(e){ previewHTML += `<pre style="color:red">Error rendering markdown: ${e.message}</pre>`}
                                        break;
                                    case 'video':
                                        if (props.url && props.url.trim()) {
                                            if (props.url.includes("youtube.com/watch?v=") || props.url.includes("youtu.be/")) {
                                                const videoId = props.url.includes("youtu.be/") ? props.url.split("youtu.be/")[1].split("?")[0] : props.url.split("v=")[1].split("&")[0];
                                                previewHTML += `<div class="video-container-preview" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background:#000; border-radius:5px;"><iframe src="https://www.youtube.com/embed/${videoId}" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" allowfullscreen></iframe></div>`;
                                            } else { previewHTML += `<div class="video-container-preview"><video controls width="100%"><source src="${props.url}">Not supported.</video></div>`; }
                                        } else if (lesson.file_path) {
                                            const videoFileUrl = "{{ url_for('static', filename='placeholder.mp4') }}".replace('placeholder.mp4', (lesson.file_path.startsWith('static/') ? lesson.file_path.substring(7) : lesson.file_path).replace(/\\\\/g, '/'));
                                            previewHTML += `<div class="video-container-preview"><p style="color:#aaa;"><i>Video File: ${lesson.file_path.split('/').pop()}</i></p><video controls width="100%"><source src="${videoFileUrl}" type="video/${lesson.file_path.split('.').pop()}">Not supported.</video></div>`;
                                        } else { previewHTML += `<p style="color:#aaa;"><i>Video content not configured.</i></p>`; }
                                        if(props.duration) previewHTML += `<p style="font-size:0.8em; color:#aaa; margin-top:5px;">Duration: ${props.duration}</p>`;
                                        break;
                                    case 'quiz':
                                        previewHTML += `<div style="border:1px solid #444; padding:10px; border-radius:4px;"><strong>Quiz:</strong> ${props.question || 'N/A'}`;
                                        if (props.options && props.options.length > 0) {
                                            previewHTML += `<ul style="margin-top:5px; padding-left:20px;">`;
                                            props.options.forEach(opt => previewHTML += `<li>${opt}</li>`);
                                            previewHTML += `</ul>`;
                                        } previewHTML += `</div>`; break;
                                    case 'download':
                                        if (lesson.file_path) {
                                            const downloadFileUrl = "{{ url_for('static', filename='placeholder.zip') }}".replace('placeholder.zip', (lesson.file_path.startsWith('static/') ? lesson.file_path.substring(7) : lesson.file_path).replace(/\\\\/g, '/'));
                                            previewHTML += `<p><a href="${downloadFileUrl}" download class="download-btn" style="opacity:1; cursor:pointer; background-color:#4CAF50;">Download: ${lesson.file_path.split('/').pop()}</a></p>`;
                                        } else { previewHTML += `<p style="color:#aaa;"><i>Downloadable file not configured.</i></p>`; }
                                        break;
                                    default: previewHTML += `<p style="color:#aaa;"><i>Preview for '${lesson.content_type}' not fully implemented.</i></p>`;
                                }
                                previewHTML += `</li>`;
                            });
                            previewHTML += '</ul>';
                        } else { previewHTML += '<p style="margin-left:20px; font-style:italic; color:#aaa;">No lessons in this module.</p>'; }
                        previewHTML += `</div>`;
                    });
                } else { previewHTML += '<p style="font-style:italic; color:#aaa; text-align:center; margin-top:20px;">This course has no modules defined yet.</p>';}
                previewHTML += `</div>`;
                previewAreaElement.innerHTML = previewHTML;
            }

            let selectedCourseId = null;
            const courseListUl = document.getElementById('course-list');
            const newCourseBtn = document.getElementById('new-course-btn');
            const currentCourseTitleEl = document.getElementById('current-course-title');
            const courseSettingsForm = document.getElementById('course-settings-form');
            const settingCourseTitleInput = document.getElementById('setting-course-title');
            const settingCourseDescriptionInput = document.getElementById('setting-course-description');
            const settingCourseDifficultyInput = document.getElementById('setting-course-difficulty');
            const settingCourseDurationInput = document.getElementById('setting-course-duration');
            const settingCourseIncomeInput = document.getElementById('setting-course-income');
            const saveCourseSettingsBtn = document.getElementById('save-course-settings-btn');

            async function fetchCourses() {
                try {
                    const response = await fetch('/api/teacher/courses');
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    const courses = await response.json();
                    renderCourseList(courses);
                } catch (error) { console.error("Failed to fetch courses:", error); courseListUl.innerHTML = '<li>Error loading courses.</li>';}
            }

            function renderCourseList(courses) {
                courseListUl.innerHTML = '';
                if (courses.length === 0) { courseListUl.innerHTML = '<li>No courses yet. Create one!</li>'; return; }
                courses.forEach(course => {
                    const li = document.createElement('li');
                    li.textContent = course.name;
                    li.style.cursor = 'pointer'; li.style.padding = '5px 0'; li.dataset.courseId = course.id;
                    li.addEventListener('click', () => loadCourse(course.id, course.name));
                    courseListUl.appendChild(li);
                });
            }

            let currentCourseData = null;

            async function loadCourse(courseId, courseName) {
                selectedCourseId = courseId; window.selectedCourseId = courseId;
                currentCourseTitleEl.textContent = `Editing: ${courseName}`;
                document.getElementById('course-canvas-main').innerHTML = '<p>Loading course content...</p>';
                propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit its properties.</p>';
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                try {
                    const courseResponse = await fetch(`/api/teacher/courses/${courseId}`);
                    if (!courseResponse.ok) throw new Error(`HTTP error! status: ${courseResponse.status} (fetching course)`);
                    currentCourseData = await courseResponse.json();
                    renderCourseContent(currentCourseData.lessons || [], currentCourseData.modules || []);
                    if (document.querySelector('.tab[data-tab="settings"]').classList.contains('active')) populateCourseSettingsForm(currentCourseData);
                    if (document.querySelector('.tab[data-tab="preview"]').classList.contains('active')) renderCoursePreview(currentCourseData, document.getElementById('course-preview-canvas'));
                } catch (error) {
                    console.error(`Failed to load course content for ${courseName}:`, error);
                    document.getElementById('course-canvas-main').innerHTML = `<p>Error loading content for ${courseName}: ${error.message}</p>`;
                    currentCourseData = null;
                }
            }

            function renderCourseContent(lessons, modules) {
                const canvas = document.getElementById('course-canvas-main');
                canvas.innerHTML = '';
                if (!modules || modules.length === 0) { canvas.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">This course has no modules. <br><button onclick="document.getElementById(\'add-new-module-btn\').click();" style="margin-top:10px;">Add First Module</button></p>'; return; }
                const sortedModules = [...modules].sort((a,b) => a.order_index - b.order_index);
                sortedModules.forEach(module => {
                    const moduleDiv = document.createElement('div');
                    Object.assign(moduleDiv, { className: 'module-container', dataset: { moduleId: module.id, moduleOrderIndex: module.order_index }, draggable: true, style: "cursor:move; border:1px dashed #777; padding:15px; margin-bottom:15px; border-radius:5px;" });
                    moduleDiv.addEventListener('dragstart', (e) => { if (e.target === moduleDiv) { draggedModuleId = module.id; e.dataTransfer.setData('text/module-id', module.id); e.target.style.opacity = '0.5'; e.target.classList.add('dragging-item'); draggedLessonId = null; }});
                    moduleDiv.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                               <h3 style="color:#81C784; margin-top:0; margin-bottom:0;">${module.name}</h3>
                                               <div>
                                                   <button class="edit-module-btn" data-module-id="${module.id}" data-module-name="${module.name}" data-module-desc="${module.description || ''}" data-module-order="${module.order_index}" style="font-size:0.8em; padding:3px 8px; margin-right: 5px;">Edit Module</button>
                                                   <button class="delete-module-btn" data-module-id="${module.id}" style="font-size:0.8em; padding:3px 8px; background-color:#d9534f;">Delete Module</button>
                                               </div>
                                           </div>`;
                    const lessonsInModule = (lessons || []).filter(l => l.module_id === module.id).sort((a,b) => a.order_index - b.order_index);
                    const lessonsContainer = document.createElement('div');
                    lessonsContainer.className = 'lessons-in-module-container';
                    if (lessonsInModule.length === 0) lessonsContainer.innerHTML = '<p style="font-style:italic; color:#aaa;">No lessons in this module yet.</p>';
                    lessonsInModule.forEach(lesson => {
                        const lessonDiv = document.createElement('div');
                        Object.assign(lessonDiv, { className: 'lesson-element-item', draggable: true, dataset: { lessonId: lesson.id, moduleId: module.id, originalOrder: lesson.order_index }, style: "border:1px solid #555; padding:8px; margin-bottom:5px; border-radius:4px; background-color:rgba(255,255,255,0.05); cursor:grab;" });
                        let lessonContentHTML = `<div style="display:flex; justify-content:space-between; align-items:center;"><span><strong>${lesson.lesson}</strong> <span style="font-size:0.8em; color:#ccc;">(${lesson.content_type})</span></span>`;
                        const controlsDiv = document.createElement('div'); controlsDiv.style.whiteSpace = 'nowrap';
                        const upButton = document.createElement('button'); Object.assign(upButton, { innerHTML: '&#x25B2;', title: "Move Up", style: "margin-left:10px; padding:2px 5px;", onclick: (e) => { e.stopPropagation(); moveLesson(lesson.id, 'up'); } });
                        const downButton = document.createElement('button'); Object.assign(downButton, { innerHTML: '&#x25BC;', title: "Move Down", style: "margin-left:5px; padding:2px 5px;", onclick: (e) => { e.stopPropagation(); moveLesson(lesson.id, 'down'); } });
                        controlsDiv.append(upButton, downButton);
                        lessonDiv.innerHTML = lessonContentHTML; lessonDiv.appendChild(controlsDiv);
                        lessonDiv.addEventListener('click', (e) => { if(!e.target.closest('button')) selectLessonElement(lesson); });
                        lessonDiv.addEventListener('dragstart', (e) => { e.stopPropagation(); draggedLessonId = lesson.id; draggedLessonOriginalModuleId = lesson.module_id; e.dataTransfer.setData('text/lesson-id', lesson.id); e.target.style.opacity = '0.5'; e.target.classList.add('dragging-item'); draggedModuleId = null; });
                        lessonsContainer.appendChild(lessonDiv);
                    });
                    moduleDiv.appendChild(lessonsContainer);
                    canvas.appendChild(moduleDiv);
                });
            }

            let currentSelectedLesson = null; let easyMDEInstance = null;
            const propertiesEditor = document.getElementById('properties-editor');

            function selectLessonElement(lessonData) {
                currentSelectedLesson = lessonData;
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                document.querySelectorAll('.lesson-element-item').forEach(el => { el.style.backgroundColor = 'rgba(255,255,255,0.05)'; el.style.border = '1px solid #555'; });
                const selectedDiv = document.querySelector(`.lesson-element-item[data-lesson-id='${lessonData.id}']`);
                if(selectedDiv) { selectedDiv.style.backgroundColor = 'rgba(76,175,80,0.2)'; selectedDiv.style.border = '1px solid #4CAF50';}
                renderPropertiesForm(lessonData);
            }

            function renderPropertiesForm(lesson) {
                propertiesEditor.innerHTML = '';
                if (easyMDEInstance) { easyMDEInstance.toTextArea(); easyMDEInstance = null; }
                const form = document.createElement('form');
                Object.assign(form, { id: 'lesson-properties-form', style: "padding:5px;", onsubmit: (e) => { e.preventDefault(); handleUpdateLesson(); } });
                form.innerHTML = `<h4 style="margin-bottom:15px;">Edit: ${lesson.lesson}</h4><input type="hidden" name="lesson_id" value="${lesson.id}"><div class="form-group"><label for="prop-lesson-title">Lesson Title:</label><input type="text" id="prop-lesson-title" name="lesson_title" value="${lesson.lesson}" required style="width:95%;"></div>`;
                let moduleDropdownHTML = '<div class="form-group"><label for="prop-module-id">Module:</label><select id="prop-module-id" name="module_id" required style="width:95%;">';
                if (currentCourseData && currentCourseData.modules) currentCourseData.modules.forEach(mod => { moduleDropdownHTML += `<option value="${mod.id}" ${lesson.module_id === mod.id ? 'selected':''}>${mod.name}</option>`; });
                else moduleDropdownHTML += `<option value="${lesson.module_id}" selected>${lesson.module_name || 'Unknown'}</option>`;
                moduleDropdownHTML += '</select></div>'; form.innerHTML += moduleDropdownHTML;
                form.innerHTML += `<div class="form-group"><label for="prop-order-index">Order Index:</label><input type="number" id="prop-order-index" name="order_index" value="${lesson.order_index}" min="1" required style="width:95%;"></div><div class="form-group"><label>Content Type:</label><input type="text" value="${lesson.content_type}" readonly style="width:95%;background-color:#333;"><input type="hidden" name="content_type" value="${lesson.content_type}"></div>`;
                switch (lesson.content_type) {
                    case 'text': const tid = `easymde-editor-prop`; form.innerHTML += `<div class="form-group"><label for="${tid}">Markdown Content:</label><textarea id="${tid}" name="markdown_content_editor">${lesson.element_properties.markdown_content||''}</textarea></div>`; setTimeout(() => { if(document.getElementById(tid)) easyMDEInstance = new EasyMDE({element:document.getElementById(tid), spellChecker:false, status:false, initialValue:lesson.element_properties.markdown_content||'', toolbar:["bold","italic","heading","|","quote","unordered-list","ordered-list","|","link","image","|","preview","side-by-side","fullscreen"]});},0); break;
                    case 'video':
                        form.innerHTML += `<div class="form-group"><label for="prop-video-url">Video URL:</label><input id="prop-video-url" type="url" name="video_url" value="${lesson.element_properties.url||''}" style="width:95%;"></div><div class="form-group"><label for="prop-video-duration">Duration:</label><input id="prop-video-duration" type="text" name="video_duration" value="${lesson.element_properties.duration||''}" style="width:95%;"></div>`;
                        if(lesson.file_path) form.innerHTML += `<div class="form-group" id="current-video-file-display-${lesson.id}"><p style="font-size:0.85em;color:#ccc;">File: <strong>${lesson.file_path.split('/').pop()}</strong> <button type="button" class="clear-file-btn" data-lesson-id="${lesson.id}" data-for-input="prop-video-file" data-display-id="selected-video-file-name-${lesson.id}" data-label-id="prop-video-file-label-${lesson.id}" style="font-size:0.8em;padding:2px 5px;background-color:#777;margin-left:5px;">Clear</button></p></div>`;
                        form.innerHTML += `<div class="form-group"><label for="prop-video-file" id="prop-video-file-label-${lesson.id}">${lesson.file_path?'Replace':'Upload'} Video File:</label><input id="prop-video-file" type="file" name="file" accept="video/*" onchange="displaySelectedFileName(this,'selected-video-file-name-${lesson.id}')"></div><p id="selected-video-file-name-${lesson.id}" style="font-size:0.8em;color:#81C784;"></p>`;
                        break;
                    case 'quiz': form.innerHTML += `<div class="form-group"><label for="prop-quiz-question">Question:</label><textarea id="prop-quiz-question" name="quiz_question" rows="3" style="width:95%;">${lesson.element_properties.question||''}</textarea></div><div class="form-group"><label for="prop-quiz-options">Options (one/line):</label><textarea id="prop-quiz-options" name="quiz_options" rows="4" style="width:95%;">${(lesson.element_properties.options||[]).join('\\n')}</textarea></div><div class="form-group"><label for="prop-quiz-correct">Correct Index (0-based):</label><input id="prop-quiz-correct" type="number" name="quiz_correct_answer_index" value="${lesson.element_properties.correct_answer_index||0}" min="0" style="width:95%;"></div>`; break;
                    case 'download':
                        if(lesson.file_path) form.innerHTML += `<div class="form-group" id="current-download-file-display-${lesson.id}"><p style="font-size:0.85em;color:#ccc;">File: <strong>${lesson.file_path.split('/').pop()}</strong> <button type="button" class="clear-file-btn" data-lesson-id="${lesson.id}" data-for-input="prop-download-file" data-display-id="selected-download-file-name-${lesson.id}" data-label-id="prop-download-file-label-${lesson.id}" style="font-size:0.8em;padding:2px 5px;background-color:#777;margin-left:5px;">Clear</button></p></div>`;
                        form.innerHTML += `<div class="form-group"><label for="prop-download-file" id="prop-download-file-label-${lesson.id}">${lesson.file_path?'Replace':'Upload'} File:</label><input id="prop-download-file" type="file" name="file" onchange="displaySelectedFileName(this,'selected-download-file-name-${lesson.id}')"></div><p id="selected-download-file-name-${lesson.id}" style="font-size:0.8em;color:#81C784;"></p>`;
                        break;
                }
                form.innerHTML += '<button type="submit" class="btn-primary" style="margin-right:10px;width:auto;padding:0.6em 1.2em;">Update Lesson</button>';
                const deleteBtn = document.createElement('button'); Object.assign(deleteBtn, {type:'button', textContent:'Delete Lesson', className:'btn-primary', style:"background-color:#d9534f;width:auto;padding:0.6em 1.2em;", onclick:()=>handleDeleteLesson()}); form.appendChild(deleteBtn);
                propertiesEditor.appendChild(form);
            }

            async function handleDeleteLesson() {
                if (!currentSelectedLesson || !confirm(`Delete "${currentSelectedLesson.lesson}"?`)) return;
                try {
                    const response = await fetch(`/api/teacher/lessons/${currentSelectedLesson.id}`,{method:'DELETE'});
                    if (!response.ok) throw new Error((await response.json()).error || 'Failed to delete');
                    alert('Lesson deleted!');
                    if(selectedCourseId && currentCourseData) loadCourse(selectedCourseId, currentCourseData.name);
                    propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit.</p>';
                    currentSelectedLesson = null; if (easyMDEInstance){easyMDEInstance.toTextArea(); easyMDEInstance=null;}
                } catch (error) { console.error("Failed to delete lesson:",error); alert(`Error: ${error.message}`); }
            }

            async function handleUpdateLesson() {
                if (!currentSelectedLesson) return;
                const form = document.getElementById('lesson-properties-form');
                const formData = new FormData(form);
                if (form.querySelector('input[name="clear_file_flag"]')?.value === 'true') {
                    formData.append('clear_file', 'true');
                }

                let elementProps = {};
                switch (currentSelectedLesson.content_type) {
                    case 'text': elementProps.markdown_content = easyMDEInstance ? easyMDEInstance.value() : formData.get('markdown_content_editor'); break;
                    case 'video': elementProps.url = formData.get('video_url'); elementProps.duration = formData.get('video_duration'); break;
                    case 'quiz': elementProps.question = formData.get('quiz_question'); elementProps.options = formData.get('quiz_options').split('\\n').map(o=>o.trim()).filter(o=>o); elementProps.correct_answer_index = parseInt(formData.get('quiz_correct_answer_index')); break;
                }
                formData.append('element_properties', JSON.stringify(elementProps));
                ['markdown_content_editor','video_url','video_duration','quiz_question','quiz_options','quiz_correct_answer_index'].forEach(k=>formData.delete(k));
                try {
                    const response = await fetch(`/api/teacher/lessons/${currentSelectedLesson.id}`, {method:'PUT', body:formData});
                    if (!response.ok) throw new Error((await response.json()).error || 'Failed to update');
                    alert('Lesson updated!');
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId, currentCourseData.name);
                    propertiesEditor.innerHTML = '<p style="text-align:center; color:#777; margin-top:30px;">Select an element to edit.</p>';
                    currentSelectedLesson=null; if(easyMDEInstance){easyMDEInstance.toTextArea();easyMDEInstance=null;}
                } catch (error) { console.error("Failed to update lesson:", error); alert(`Error: ${error.message}`); }
            }

            function populateCourseSettingsForm(course) {
                settingCourseTitleInput.value = course.name || '';
                settingCourseDescriptionInput.value = course.description || '';
                const settings = course.course_settings || {};
                settingCourseDifficultyInput.value = settings.difficulty || 'Intermediate';
                settingCourseDurationInput.value = settings.duration || '';
                settingCourseIncomeInput.value = settings.income_potential || '';
            }

            async function loadCourseSettings(courseId) {
                if (!courseId) return;
                if (currentCourseData && currentCourseData.id === courseId) { populateCourseSettingsForm(currentCourseData); return; }
                try {
                    const response = await fetch(`/api/teacher/courses/${courseId}`);
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    populateCourseSettingsForm(await response.json());
                } catch (error) { console.error("Failed to load course settings:", error); alert("Error loading course settings.");}
            }

            newCourseBtn.addEventListener('click', () => {
                const formHTML = `<form id="new-course-modal-form" style="display:flex;flex-direction:column;gap:10px;"><div class="form-group"><label for="modal-course-name">Name:</label><input type="text" id="modal-course-name" name="name" r style="width:98%;"></div><div class="form-group"><label for="modal-course-description">Description:</label><textarea id="modal-course-description" name="description" rows="3" style="width:98%;"></textarea></div><div class="form-group"><label for="modal-course-difficulty">Difficulty:</label><select id="modal-course-difficulty" name="difficulty" style="width:98%;"><option value="Beginner">Beginner</option><option value="Intermediate" selected>Intermediate</option><option value="Advanced">Advanced</option></select></div><div class="form-group"><label for="modal-course-duration">Est. Duration:</label><input type="text" id="modal-course-duration" name="duration" style="width:98%;"></div><div class="form-group"><label for="modal-course-income">Income Potential:</label><input type="text" id="modal-course-income" name="income_potential" style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Create Course</button></form>`;
                const submitNewCourse = async (formData, closeModalCallback) => {
                    const s = {difficulty:formData.get('difficulty'),duration:formData.get('duration'),income_potential:formData.get('income_potential')};
                    try {
                        const response = await fetch('/api/teacher/courses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:formData.get('name'),description:formData.get('description'),settings:s})});
                        if(!response.ok)throw new Error((await response.json()).error || 'Failed to create');
                        fetchCourses(); alert('Course created!'); if(closeModalCallback)closeModalCallback();
                    } catch (error) { console.error("Failed to create course:",error);alert(`Error: ${error.message}`);}
                };
                openModal("Create New Course", formHTML, submitNewCourse);
            });

            saveCourseSettingsBtn.addEventListener('click', async () => {
                if (!selectedCourseId) { alert("No course selected."); return; }
                const payload = {name:settingCourseTitleInput.value,description:settingCourseDescriptionInput.value,settings:{difficulty:settingCourseDifficultyInput.value,duration:settingCourseDurationInput.value,income_potential:settingCourseIncomeInput.value}};
                try {
                    const response = await fetch(`/api/teacher/courses/${selectedCourseId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
                    if(!response.ok) throw new Error((await response.json()).error || 'Failed to save');
                    alert('Settings saved!'); fetchCourses(); currentCourseTitleEl.textContent = `Editing: ${payload.name}`;
                    if(currentCourseData&&currentCourseData.id===selectedCourseId){currentCourseData.name=payload.name;currentCourseData.description=payload.description;currentCourseData.course_settings=payload.settings;}
                } catch (error) { console.error("Failed to save settings:",error);alert(`Error: ${error.message}`);}
            });

            const addNewModuleBtn = document.getElementById('add-new-module-btn');
            addNewModuleBtn.addEventListener('click', () => {
                if (!selectedCourseId) { alert("Select a course first."); return; }
                const order = (currentCourseData&&currentCourseData.modules)?currentCourseData.modules.length+1:1;
                const formHTML = `<form id="add-module-modal-form" style="display:flex;flex-direction:column;gap:10px;"><div class="form-group"><label for="modal-module-name">Name:</label><input type="text" id="modal-module-name" name="name" r style="width:98%;"></div><div class="form-group"><label for="modal-module-description">Description:</label><textarea id="modal-module-description" name="description" rows="3" style="width:98%;"></textarea></div><div class="form-group"><label for="modal-module-order">Order:</label><input type="number" id="modal-module-order" name="order_index" value="${order}" min="1" r style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Create Module</button></form>`;
                const submitNewModule = async (formData, closeModalCallback) => {
                    try {
                        const response = await fetch(`/api/teacher/courses/${selectedCourseId}/modules`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:formData.get('name'),description:formData.get('description'),order_index:parseInt(formData.get('order_index'))})});
                        if(!response.ok) throw new Error((await response.json()).error||'Failed to create');
                        alert('Module created!'); if(currentCourseData)loadCourse(selectedCourseId,currentCourseData.name); else fetchCourses();
                        if(closeModalCallback)closeModalCallback();
                    } catch (error) { console.error("Failed to create module:",error);alert(`Error: ${error.message}`);}
                };
                openModal("Add New Module", formHTML, submitNewModule);
            });

            const mainCanvas = document.getElementById('course-canvas-main');

            propertiesEditorEl.addEventListener('click', function(event) {
                if (event.target.classList.contains('clear-file-btn')) {
                    const button = event.target;
                    const fileInputId = button.dataset.forInput;
                    const displayId = button.dataset.displayId;
                    const labelId = button.dataset.labelId;

                    const fileInput = document.getElementById(fileInputId);
                    if (fileInput) fileInput.value = null;

                    const fileNameDisplay = document.getElementById(displayId);
                    if (fileNameDisplay) fileNameDisplay.textContent = '';

                    const form = button.closest('form');
                    if (form) {
                        let clearFlagInput = form.querySelector('input[name="clear_file_flag"]');
                        if (!clearFlagInput) {
                            clearFlagInput = document.createElement('input');
                            clearFlagInput.type = 'hidden';
                            clearFlagInput.name = 'clear_file_flag';
                            clearFlagInput.id = 'clear-file-flag-input';
                            form.appendChild(clearFlagInput);
                        }
                        clearFlagInput.value = 'true';
                    }

                    const parentP = button.closest('p');
                    if(parentP) parentP.style.display = 'none';

                    const label = document.getElementById(labelId);
                    if(label && label.textContent.includes('Replace')) label.textContent = label.textContent.replace('Replace', 'Upload');
                     else if(label && label.textContent.includes('Current')) label.textContent = label.textContent.replace('Current', 'Upload');


                } else if (event.target.classList.contains('edit-module-btn')) {
                     // Edit module buttons are on the canvas, not in properties editor. This part can be removed.
                }
            });

             mainCanvas.addEventListener('click', function(event) {
                if (event.target.classList.contains('edit-module-btn') && !event.target.closest('#properties-editor')) {
                    const button = event.target;
                    handleEditModuleClick(button.dataset.moduleId, button.dataset.moduleName, button.dataset.moduleDesc, button.dataset.moduleOrder);
                } else if (event.target.classList.contains('delete-module-btn')) {
                    const button = event.target;
                    const moduleId = button.dataset.moduleId;
                    const moduleContainer = button.closest('.module-container');
                    const moduleName = moduleContainer ? (moduleContainer.querySelector('h3')?.textContent || 'this module') : 'this module';

                    if (confirm(`Are you sure you want to delete the module "${moduleName}"? This action cannot be undone and will fail if the module contains lessons.`)) {
                        fetch(`/api/teacher/modules/${moduleId}`, {
                            method: 'DELETE',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        })
                        .then(response => {
                            if (!response.ok) {
                                // Try to parse error JSON, otherwise use status text
                                return response.json().then(err => { throw new Error(err.error || `HTTP error! Status: ${response.status}`); })
                                                   .catch(() => { throw new Error(`HTTP error! Status: ${response.status}`); });
                            }
                            return response.json();
                        })
                        .then(data => {
                            alert(data.message || 'Module deleted successfully!');
                            if (selectedCourseId && currentCourseData) {
                                loadCourse(selectedCourseId, currentCourseData.name);
                            }
                        })
                        .catch(error => {
                            console.error('Failed to delete module:', error);
                            alert(`Error deleting module: ${error.message}`);
                        });
                    }
                }
            });


            let draggedLessonId = null; let draggedLessonOriginalModuleId = null; let draggedModuleId = null;

            mainCanvas.addEventListener('dragstart', function(event) {
                const target = event.target;
                if (target.classList.contains('lesson-element-item')) {
                    draggedLessonId = target.dataset.lessonId; draggedLessonOriginalModuleId = target.dataset.moduleId;
                    event.dataTransfer.setData('text/lesson-id', draggedLessonId);
                    target.style.opacity='0.5'; target.classList.add('dragging-item'); draggedModuleId=null;
                } else if (target.classList.contains('module-container')) {
                    draggedModuleId = target.dataset.moduleId; event.dataTransfer.setData('text/module-id', draggedModuleId);
                    target.style.opacity='0.5'; target.classList.add('dragging-item'); draggedLessonId=null;
                }
            });

            mainCanvas.addEventListener('dragend', function(event) {
                const target = event.target;
                if (target.classList.contains('lesson-element-item')||target.classList.contains('module-container')) {target.style.opacity='1';target.classList.remove('dragging-item');}
                draggedLessonId=null;draggedLessonOriginalModuleId=null;draggedModuleId=null;
                document.querySelectorAll('.drop-target-highlight,.lesson-drop-indicator,.module-drop-indicator').forEach(el=>el.remove());
            });

            mainCanvas.addEventListener('dragover', function(event) {
                event.preventDefault();
                document.querySelectorAll('.lesson-drop-indicator,.module-drop-indicator,.drop-target-highlight').forEach(el=>el.remove());
                if (draggedLessonId) {
                    const ctm = event.target.closest('.module-container');
                    if (ctm) {
                        ctm.classList.add('drop-target-highlight');
                        let lip = false;
                        const lis = Array.from(ctm.querySelectorAll('.lesson-element-item'));
                        for (const i of lis) { if (i.dataset.lessonId===draggedLessonId && i.style.opacity==='0.5') continue; const r=i.getBoundingClientRect(); if (event.clientY<r.top+r.height/2){i.insertAdjacentHTML('beforebegin','<div class="lesson-drop-indicator"></div>');lip=true;break;}}
                        if (!lip) (ctm.querySelector('.lessons-in-module-container')||ctm).insertAdjacentHTML('beforeend','<div class="lesson-drop-indicator"></div>');
                    }
                } else if (draggedModuleId) {
                    const mis = Array.from(mainCanvas.querySelectorAll('.module-container'));
                    let mip = false;
                    for (const i of mis) { if (i.dataset.moduleId===draggedModuleId && i.style.opacity==='0.5') continue; const r=i.getBoundingClientRect(); if (event.clientY<r.top+r.height/2){i.insertAdjacentHTML('beforebegin','<div class="module-drop-indicator"></div>');mip=true;break;}}
                    if (!mip) { let cpae=true; if(mis.length>0&&mis[mis.length-1].dataset.moduleId===draggedModuleId&&mis.length===1){} else if(mis.length>0&&mis[mis.length-1].dataset.moduleId===draggedModuleId)cpae=false; if(cpae||mis.length===0)mainCanvas.insertAdjacentHTML('beforeend','<div class="module-drop-indicator"></div>'); else if(mis.length===1&&mis[0].dataset.moduleId===draggedModuleId&&!mainCanvas.querySelector('.module-drop-indicator'))mainCanvas.insertAdjacentHTML('afterbegin','<div class="module-drop-indicator"></div>');}
                }
            });

            function removeModuleDropIndicators(){ document.querySelectorAll('.module-drop-indicator').forEach(el=>el.remove());}
            mainCanvas.addEventListener('dragleave', function(event) {});

            mainCanvas.addEventListener('drop', async function(event) {
                event.preventDefault();
                const activeLessonDropIndicator = mainCanvas.querySelector('.lesson-drop-indicator');
                const activeModuleDropIndicator = mainCanvas.querySelector('.module-drop-indicator');
                document.querySelectorAll('.drop-target-highlight').forEach(el=>el.classList.remove('drop-target-highlight'));
                if(activeLessonDropIndicator)activeLessonDropIndicator.remove(); if(activeModuleDropIndicator)activeModuleDropIndicator.remove();

                if (draggedLessonId && currentCourseData && currentCourseData.lessons) {
                    let tcfld = event.target.closest('.module-container');
                    if(!tcfld && activeLessonDropIndicator && activeLessonDropIndicator.parentElement.classList.contains('module-container')) tcfld=activeLessonDropIndicator.parentElement;
                    if(!tcfld && activeLessonDropIndicator && activeLessonDropIndicator.parentElement.classList.contains('lessons-in-module-container')) tcfld=activeLessonDropIndicator.parentElement.closest('.module-container');
                    if(!tcfld){console.log("LDrop:No valid module container.");draggedLessonId=null;draggedLessonOriginalModuleId=null;return;}
                    const tmi = parseInt(tcfld.dataset.moduleId); const ltu=[];
                    const dl = currentCourseData.lessons.find(l=>l.id==draggedLessonId);
                    if(!dl){console.error("Dragged lesson not found.");return;}
                    const omi = dl.module_id; dl.module_id = tmi;
                    let lintm = currentCourseData.lessons.filter(l=>l.module_id===tmi && l.id!=draggedLessonId).sort((a,b)=>a.order_index-b.order_index);
                    let iai = lintm.length;
                    if (activeLessonDropIndicator) { const ne=activeLessonDropIndicator.nextElementSibling; if (ne&&ne.classList.contains('lesson-element-item')){ const nei=ne.dataset.lessonId; const fi=lintm.findIndex(l=>l.id==nei); if(fi!==-1)iai=fi;}}
                    lintm.splice(iai,0,dl);
                    lintm.forEach((l,i)=>{const noi=i+1; if(l.order_index!==noi||l.module_id!==tmi){l.order_index=noi;l.module_id=tmi;ltu.push({id:l.id,order_index:l.order_index,module_id:l.module_id});}});
                    if(omi!==tmi){currentCourseData.lessons.filter(l=>l.module_id===omi&&l.id!=draggedLessonId).sort((a,b)=>a.order_index-b.order_index).forEach((l,i)=>{const noi=i+1;if(l.order_index!==noi){l.order_index=noi;constex=ltu.find(u=>u.id===l.id);if(ex)ex.order_index=noi;else ltu.push({id:l.id,order_index:noi,module_id:l.module_id});}});}
                    if(ltu.length>0){for(const lu of ltu){try{const ur=await fetch(`/api/teacher/lessons/${lu.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_index:lu.order_index,module_id:lu.module_id})});if(!ur.ok)console.error(`Failed L${lu.id}`);}catch(e){console.error(`Error L${lu.id}`,e);}}}
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId,currentCourseData.name);
                } else if (draggedModuleId && currentCourseData && currentCourseData.modules) {
                    const mtu=[]; let cmo=[...currentCourseData.modules].sort((a,b)=>a.order_index-b.order_index);
                    const dmd=cmo.find(m=>m.id==draggedModuleId);
                    if(!dmd){console.error("Dragged module not found");return;}
                    cmo=cmo.filter(m=>m.id!=draggedModuleId);
                    let iai=cmo.length; if(activeModuleDropIndicator){const ne=activeModuleDropIndicator.nextElementSibling; if(ne&&ne.classList.contains('module-container')){const nei=ne.dataset.moduleId;const fi=cmo.findIndex(m=>m.id==nei);if(fi!==-1)iai=fi;}else if(!activeModuleDropIndicator.previousElementSibling||(activeModuleDropIndicator.previousElementSibling&&!activeModuleDropIndicator.previousElementSibling.classList.contains('module-container')))iai=0;}
                    cmo.splice(iai,0,dmd);
                    cmo.forEach((m,i)=>{const noi=i+1;if(m.order_index!==noi){m.order_index=noi;mtu.push({id:m.id,order_index:m.order_index});}});
                    if(mtu.length>0){for(const mu of mtu){try{const ur=await fetch(`/api/teacher/modules/${mu.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_index:mu.order_index})});if(!ur.ok)console.error(`Failed M${mu.id}`);}catch(e){console.error(`Error M${mu.id}`,e);}}}
                    if(selectedCourseId&&currentCourseData)loadCourse(selectedCourseId,currentCourseData.name);
                }
                draggedLessonId=null;draggedLessonOriginalModuleId=null;draggedModuleId=null;
            });

            const elementPalette = document.getElementById('element-palette');
            elementPalette.addEventListener('click', function(event) {
                if (event.target.classList.contains('element-btn') && !event.target.classList.contains('template-btn')) {
                    const elementType = event.target.dataset.type;
                    handleAddElementFromPalette(elementType);
                }
            });

            function handleAddElementFromPalette(elementType) {
                if (!selectedCourseId || !currentCourseData || !currentCourseData.modules || currentCourseData.modules.length === 0) {
                    alert("Please select a course and ensure it has at least one module before adding elements.");
                    return;
                }

                let defaultTitle = elementType.charAt(0).toUpperCase() + elementType.slice(1) + " Lesson";
                let typeSpecificFields = '';
                // Placeholder for type-specific fields - will be expanded later
                switch(elementType) {
                    case 'text': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-markdown">Initial Markdown:</label><textarea id="modal-lesson-markdown" name="markdown_content" rows="3" style="width:98%;"></textarea></div>`; break;
                    case 'video': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-video-url">Video URL (optional):</label><input type="url" id="modal-lesson-video-url" name="video_url" style="width:98%;"></div> <div class="form-group"><label for="modal-lesson-video-file">Upload Video File (optional):</label><input type="file" id="modal-lesson-video-file" name="file" accept="video/*" onchange="displaySelectedFileName(this, 'selected-new-video-file-name')"></div> <p id="selected-new-video-file-name" style="font-size:0.8em;color:#81C784;"></p>`; break;
                    case 'quiz': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-quiz-question">Question:</label><input type="text" id="modal-lesson-quiz-question" name="quiz_question" style="width:98%;"></div> <div class="form-group"><label for="modal-lesson-quiz-options">Options (one per line):</label><textarea id="modal-lesson-quiz-options" name="quiz_options" rows="3" style="width:98%;"></textarea></div> <div class="form-group"><label for="modal-lesson-quiz-correct">Correct Option Index (0-based):</label><input type="number" id="modal-lesson-quiz-correct" name="quiz_correct_answer_index" value="0" min="0" style="width:98%;"></div>`; break;
                    case 'download': typeSpecificFields = `<div class="form-group"><label for="modal-lesson-download-file">Upload File:</label><input type="file" id="modal-lesson-download-file" name="file" onchange="displaySelectedFileName(this, 'selected-new-download-file-name')"></div> <p id="selected-new-download-file-name" style="font-size:0.8em;color:#81C784;"></p>`; break;
                }

                let moduleOptionsHTML = '';
                currentCourseData.modules.sort((a,b) => a.order_index - b.order_index).forEach(mod => {
                    moduleOptionsHTML += `<option value="${mod.id}">${mod.name}</option>`;
                });
                if (!moduleOptionsHTML) {
                    alert("No modules available in this course to add a lesson to.");
                    return;
                }

                const firstModuleId = currentCourseData.modules[0].id;
                const lessonsInFirstModule = currentCourseData.lessons ? currentCourseData.lessons.filter(l => l.module_id === firstModuleId) : [];
                const defaultOrderIndex = lessonsInFirstModule.length + 1;

                const formHTML = \`<form id="add-lesson-element-modal-form" style="display:flex;flex-direction:column;gap:10px;">
                    <input type="hidden" name="content_type" value="\${elementType}">
                    <div class="form-group"><label for="modal-lesson-title">Lesson Title:</label><input type="text" id="modal-lesson-title" name="lesson_title" value="\${defaultTitle}" r style="width:98%;"></div>
                    <div class="form-group"><label for="modal-lesson-module">Parent Module:</label><select id="modal-lesson-module" name="module_id" r style="width:98%;">\${moduleOptionsHTML}</select></div>
                    <div class="form-group"><label for="modal-lesson-order">Order Index:</label><input type="number" id="modal-lesson-order" name="order_index" value="\${defaultOrderIndex}" min="1" r style="width:98%;"></div>
                    \${typeSpecificFields}
                    <button type="submit" class="btn-primary" style="width:100%;">Add Lesson Element</button>
                </form>\`;

                const submitNewLessonElement = async (formData, closeModalCallback) => {
                    if (!selectedCourseId) { alert("Error: No course selected."); return; }

                    let elementProps = {};
                    const contentType = formData.get('content_type');
                    switch(contentType) {
                        case 'text': elementProps.markdown_content = formData.get('markdown_content'); break;
                        case 'video': elementProps.url = formData.get('video_url'); break;
                        case 'quiz':
                            elementProps.question = formData.get('quiz_question');
                            elementProps.options = formData.get('quiz_options') ? formData.get('quiz_options').split('\\n').map(o=>o.trim()).filter(o=>o) : [];
                            elementProps.correct_answer_index = formData.get('quiz_correct_answer_index') ? parseInt(formData.get('quiz_correct_answer_index')) : 0;
                            break;
                    }
                    ['markdown_content', 'video_url', 'quiz_question', 'quiz_options', 'quiz_correct_answer_index'].forEach(k => formData.delete(k));
                    formData.append('element_properties', JSON.stringify(elementProps));

                    try {
                        const response = await fetch(\`/api/teacher/courses/\${selectedCourseId}/lessons\`, {
                            method: 'POST',
                            body: formData
                        });
                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'Failed to create lesson element');
                        }
                        alert('Lesson element created!');
                        if (currentCourseData) loadCourse(selectedCourseId, currentCourseData.name);
                        if (closeModalCallback) closeModalCallback();
                    } catch (error) {
                        console.error("Failed to create lesson element:", error);
                        alert(\`Error: \${error.message}\`);
                    }
                };
                openModal(\`Add New \${elementType.charAt(0).toUpperCase() + elementType.slice(1)} Element\`, formHTML, submitNewLessonElement);

                const moduleDropdownInModal = document.getElementById('modal-lesson-module');
                const orderInputInModal = document.getElementById('modal-lesson-order');
                if (moduleDropdownInModal && orderInputInModal && currentCourseData && currentCourseData.lessons) {
                    moduleDropdownInModal.addEventListener('change', function() {
                        const selectedModId = parseInt(this.value);
                        const lessonsInSelectedModule = currentCourseData.lessons.filter(l => l.module_id === selectedModId);
                        orderInputInModal.value = lessonsInSelectedModule.length + 1;
                    });
                }
            }

            function handleEditModuleClick(moduleId, name, description, orderIndex) {
                const formHTML = \`<form id="edit-module-modal-form" style="display:flex;flex-direction:column;gap:10px;"><input type="hidden" name="module_id" value="\${moduleId}"><div class="form-group"><label for="modal-edit-module-name">Name:</label><input type="text" id="modal-edit-module-name" name="name" value="\${name}" r style="width:98%;"></div><div class="form-group"><label for="modal-edit-module-description">Description:</label><textarea id="modal-edit-module-description" name="description" rows="3" style="width:98%;">\${description}</textarea></div><div class="form-group"><label for="modal-edit-module-order">Order:</label><input type="number" id="modal-edit-module-order" name="order_index" value="\${orderIndex}" min="1" r style="width:98%;"></div><button type="submit" class="btn-primary" style="width:100%;">Update Module</button></form>\`;
                const submitEditModule = async (formData, closeModalCallback) => {
                    const mId=formData.get('module_id'), uName=formData.get('name'), uDesc=formData.get('description'), uOrder=parseInt(formData.get('order_index'));
                    try {
                        const response=await fetch(`/api/teacher/modules/${mId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:uName,description:uDesc,order_index:uOrder})});
                        if(!response.ok)throw new Error((await response.json()).error||'Failed to update');
                        alert('Module updated!'); if(currentCourseData){const cName=currentCourseData.id===selectedCourseId?currentCourseData.name:document.querySelector(`#course-list li[data-course-id='${selectedCourseId}']`).textContent;loadCourse(selectedCourseId,cName);}
                        if(closeModalCallback)closeModalCallback();
                    } catch(error){console.error("Failed to update module:",error);alert(`Error: ${error.message}`);}
                };
                openModal(`Edit Module: ${name}`, formHTML, submitEditModule);
            }

        </script>
    </body>
    </html>
    """)