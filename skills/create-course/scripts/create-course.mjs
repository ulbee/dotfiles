#!/usr/bin/env node
// Заведение мультиязычного курса в LMS через Django-admin (только testing).
// Драйвит admin браузером под storageState робота (как *.mjs в корне проекта LMS).
//
// Использование:
//   node create-course.mjs --tms-id 887 --languages ru,en --curator yusokolova \
//        [--publish|--no-publish] [--modules 2] [--name-base TMSLV] [--apply]
//
// Без --apply — DRY-RUN: печатает план, ничего не пишет.
// Окружение и пути к проекту берутся из LMS_PROJECT_DIR (по умолчанию — путь ниже).

import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { existsSync } from 'node:fs';

const PROJECT_DIR =
    process.env.LMS_PROJECT_DIR || '/Users/yusokolova/arcadia4/hrtech/frontend/services/lms';
const ADMIN_BASE = 'https://testing.admin.lms.yandex-team.ru';
const STORAGE_STATE = path.join(PROJECT_DIR, 'tests/playwright/tests/auth/teardownUser.json');
const USERS_MODEL = '/admin/users/user/'; // FK-цель для author и tutor.user

// --- аргументы ---
const DEFAULT_CURATOR = 'robot-lms-hermione'; // «сам робот» — куратор/author по умолчанию
const DEFAULT_CATEGORY = 'Языки программирования'; // «программирование»; в admin — M2M «Категории» (coursecategory)
const DEFAULT_STUDY_MODE = '37'; // Самостоятельно (форма обучения)
const DEFAULT_START_MODE = 'any_time'; // В любое время («обучение от»)
const DEFAULT_PAYMENT = 'free'; // Бесплатно (способ оплаты)
const VIDEO_URL_PLACEHOLDER = 'https://example.com/replace-me'; // url обязателен в admin; реальную ссылку приложит пользователь

function parseArgs(argv) {
    const a = { languages: [], nameBase: 'TMSLV', publish: null, apply: false };
    for (let i = 0; i < argv.length; i += 1) {
        const k = argv[i];
        const next = () => argv[(i += 1)];
        switch (k) {
            case '--tms-id': a.tmsId = next(); break;
            case '--languages': a.languages = next().split(',').map((s) => s.trim().toLowerCase()).filter(Boolean); break;
            case '--curator': a.curator = next(); break;
            // --modules: число (N статей) ИЛИ список типов через запятую, напр. "article,article,video".
            case '--modules': a.moduleSpec = next(); break;
            case '--category': a.category = next(); break;    // название категории (coursecategory) или её id
            case '--study-mode': a.studyMode = next(); break; // id study_mode (37=самостоятельно)
            case '--start-mode': a.startMode = next(); break; // any_time|after_group_filled|fixed_dates
            case '--payment': a.payment = next(); break;      // free|corporate|personal
            case '--count': a.count = Number(next()); break;  // порядковый № курса в кейсе (когда их несколько)
            case '--name-base': a.nameBase = next(); break;
            case '--publish': a.publish = true; break;
            case '--no-publish': a.publish = false; break;
            case '--apply': a.apply = true; break;
            case '--force': a.force = true; break; // удалить существующий курс с таким slug перед созданием
            case '--slug': a.slug = next(); break; // override
            default: console.error(`Неизвестный аргумент: ${k}`); process.exit(2);
        }
    }
    return a;
}

// Разбор спецификации модулей → массив {type, name, weight, content?|url?, estimatedTime}.
function buildModules(spec) {
    const raw = spec == null ? '2' : String(spec).trim();
    const types = /^\d+$/.test(raw) ? Array.from({ length: Number(raw) }, () => 'article') : raw.split(',').map((s) => s.trim().toLowerCase());
    return types.map((type, n) => {
        const weight = n + 1;
        if (type === 'article') return { type, name: `Статья ${weight}`, weight, content: `Текст статьи ${weight}`, estimatedTime: 60 };
        if (type === 'video') return { type, name: `Видео ${weight}`, weight, url: VIDEO_URL_PLACEHOLDER, estimatedTime: 60 };
        if (type === 'scorm') throw new Error('scorm пока не поддерживается (форма admin требует загрузку пакета) — создай scorm-модуль вручную; типы: article|video');
        throw new Error(`неизвестный тип модуля '${type}' (поддерживаются: article, video)`);
    });
}

function buildPlan(a) {
    if (!a.tmsId) throw new Error('--tms-id обязателен (номер TMS-кейса)');
    if (!a.languages.length) throw new Error('--languages обязателен (напр. ru,en) — порядок важен');
    if (a.publish === null) throw new Error('укажи --publish или --no-publish (из описания ТК)');

    // Когда кейс описывает несколько курсов — нумеруем: slug slug_tmslv{id}_{count}, имя {base}{id}_{count}.
    // Без --count (один курс) — суффикса нет.
    if (a.count != null && !Number.isInteger(a.count)) throw new Error('--count должен быть целым числом');
    const suffix = a.count != null ? `_${a.count}` : '';
    const slug = a.slug || `slug_tmslv${a.tmsId}${suffix}`;
    const nameRu = `${a.nameBase}${a.tmsId}${suffix}`;
    const cards = a.languages.map((code) => ({
        code,
        name: `${a.nameBase}${a.tmsId}${suffix} ${code.toUpperCase()}`,
        targetAudience: `Аудитория курса (${code.toUpperCase()})`,
        outcomes: [{ title: `Навык (${code.toUpperCase()})`, description: '' }],
    }));
    const modules = buildModules(a.moduleSpec);
    return {
        slug,
        nameRu,
        languages: a.languages,
        curator: a.curator || DEFAULT_CURATOR,
        publish: a.publish,
        courseType: 'course',
        structure: modules.length > 1 ? 'multi_modules' : modules.length === 1 ? 'single_module' : 'no_modules',
        completionThreshold: 100,
        paidPercent: 0,
        category: a.category || DEFAULT_CATEGORY,
        studyMode: a.studyMode || DEFAULT_STUDY_MODE,
        startMode: a.startMode || DEFAULT_START_MODE,
        paymentMethod: a.payment || DEFAULT_PAYMENT,
        force: a.force || false,
        cards,
        modules,
    };
}

function printPlan(plan) {
    console.log('=== ПЛАН СОЗДАНИЯ КУРСА (testing) ===');
    console.log(`slug:            ${plan.slug}`);
    console.log(`name_ru:         ${plan.nameRu}`);
    console.log(`course_type:     ${plan.courseType}`);
    console.log(`structure:       ${plan.structure}`);
    console.log(`migrated_to_ML:  true`);
    console.log(`languages (order): ${plan.languages.join(', ')}`);
    console.log(`curator/author:  ${plan.curator}`);
    console.log(`категория:       ${plan.category}  (M2M «Категории»; каскадной подкатегории в admin нет)`);
    console.log(`форма обучения:  study_mode=${plan.studyMode} (37=самостоятельно)`);
    console.log(`обучение от:     start_mode=${plan.startMode}`);
    console.log(`способ оплаты:   payment_method=${plan.paymentMethod}`);
    console.log(`publish:         ${plan.publish ? 'ДА (is_active + show_in_catalog + show_in_lab)' : 'НЕТ (черновик)'}`);
    console.log('\nКарточки по языкам (название / кому подойдёт / чему научитесь):');
    for (const c of plan.cards) console.log(`  [${c.code}] name="${c.name}"  кому подойдёт="${c.targetAudience}"  outcomes=${c.outcomes.length}`);
    console.log('\nМодули (заполняются на всех языках):');
    for (const m of plan.modules) {
        const extra = m.type === 'video' ? `url=${m.url} (замени вручную)` : `content="${m.content}"`;
        console.log(`  weight=${m.weight}  [${m.type}] "${m.name}"  ${m.estimatedTime}м  ${extra}`);
    }
    console.log('\n(dry-run: ничего не записано. Для реального создания добавь --apply)');
}

// --- playwright из node_modules проекта ---
async function loadChromium() {
    const pw = path.join(PROJECT_DIR, 'node_modules/@playwright/test/index.js');
    if (!existsSync(pw)) throw new Error(`@playwright/test не найден в ${PROJECT_DIR}/node_modules`);
    const mod = await import(pathToFileURL(pw).href);
    const chromium = mod.chromium ?? mod.default?.chromium;
    if (!chromium) throw new Error('Не удалось получить chromium из @playwright/test');
    return chromium;
}

// --- admin helpers ---
async function saveForm(page, label) {
    await Promise.all([
        page.waitForURL((u) => !u.toString().includes('/add/'), { timeout: 30000 }).catch(() => {}),
        page.locator('input[name="_save"]').click(),
    ]);
    const err = await page.locator('.errornote, .errorlist li').first().innerText().catch(() => '');
    if (page.url().includes('/add/') || err) throw new Error(`${label}: ${err || 'форма не сохранилась (остались на /add/)'}`);
}

async function resolveUserId(page, login) {
    if (/^\d+$/.test(login)) return login;
    await page.goto(`${ADMIN_BASE}${USERS_MODEL}?q=${encodeURIComponent(login)}`, { waitUntil: 'domcontentloaded' });
    const href = await page.locator('#result_list tbody tr a').first().getAttribute('href').catch(() => null);
    const m = href && href.match(/\/user\/(\d+)\/change/);
    if (!m) throw new Error(`Не найден пользователь '${login}' в ${USERS_MODEL}`);
    return m[1];
}

async function resolveLangPk(page, courseId, code) {
    await page.goto(`${ADMIN_BASE}/admin/courses/courselanguage/?course=${courseId}&language=${code}`, { waitUntil: 'domcontentloaded' });
    const pk = await page.locator('#result_list tbody tr input[name="_selected_action"]').first().getAttribute('value').catch(() => null);
    if (!pk) throw new Error(`Не найден pk CourseLanguage для '${code}' (курс ${courseId})`);
    return pk;
}

// Поиск ?q=slug — подстрочный (slug_tmslv887 матчит и slug_tmslv887_2), поэтому
// сверяем ТОЧНЫЙ slug через #id_slug на change-форме каждого кандидата.
async function findExactCourseId(page, slug) {
    await page.goto(`${ADMIN_BASE}/admin/courses/course/?q=${encodeURIComponent(slug)}`, { waitUntil: 'domcontentloaded' });
    const hrefs = await page
        .locator('#result_list tbody tr a[href*="/change/"]')
        .evaluateAll((as) => as.map((a) => a.getAttribute('href')))
        .catch(() => []);
    const ids = [...new Set(hrefs.map((h) => (h && h.match(/\/course\/(\d+)\/change/) || [])[1]).filter(Boolean))];
    for (const id of ids) {
        await page.goto(`${ADMIN_BASE}/admin/courses/course/${id}/change/`, { waitUntil: 'domcontentloaded' });
        const s = await page.locator('#id_slug').inputValue().catch(() => '');
        if (s === slug) return id;
    }
    return null;
}

async function deleteCourseBySlug(page, slug) {
    const id = await findExactCourseId(page, slug);
    if (!id) return null;
    await page.goto(`${ADMIN_BASE}/admin/courses/course/${id}/delete/`, { waitUntil: 'domcontentloaded' });
    // Кнопка подтверждения может быть <input type=submit> или <button type=submit>;
    // берём первую submit-кнопку внутри формы удаления.
    const confirm = page
        .locator('form input[type="submit"], form button[type="submit"], [name="post"]')
        .first();
    await confirm.click({ timeout: 15000 });
    await page.waitForLoadState('domcontentloaded');
    // после удаления не должно остаться точного совпадения
    const still = await findExactCourseId(page, slug);
    if (still) throw new Error(`не удалось удалить курс '${slug}' (id=${id}) — возможно, есть защищённые связи`);
    return id;
}

// Выбор категории (M2M «Категории» = coursecategory) по названию или id. Каскадной подкатегории
// (как в конструкторе Лабы) в admin нет — здесь задаётся только категория.
async function selectCategory(page, category, log) {
    if (!category) return;
    const byId = /^\d+$/.test(category);
    const pick = byId ? category : { label: category };
    // Django filter_horizontal: видимый select «доступные» = #id_categories_from, кнопка добавления =
    // #id_categories_add_link; при submit отправляется содержимое скрытого #id_categories.
    try {
        await page.selectOption('#id_categories_from', pick, { timeout: 8000 });
        await page.click('#id_categories_add_link', { timeout: 8000 });
        return;
    } catch {
        // fallback: обычный multiple select без filter_horizontal
        try {
            await page.selectOption('#id_categories', pick, { timeout: 8000 });
            return;
        } catch (e) {
            log(`  ⚠ категория '${category}' не выбрана (${(e.message || '').split('\n')[0]})`);
        }
    }
}

// id модуля по имени в рамках курса — после сохранения Django редиректит на changelist,
// поэтому находим запись фильтром ?course= и по имени. model: 'textresource' | 'videoresource'.
async function resolveModuleId(page, courseId, name, model = 'textresource') {
    await page.goto(`${ADMIN_BASE}/admin/resources/${model}/?course=${courseId}`, { waitUntil: 'domcontentloaded' });
    const rows = page.locator('#result_list tbody tr');
    const n = await rows.count().catch(() => 0);
    const re = new RegExp(`/${model}/(\\d+)/`);
    // Название модуля — это текст ссылки на change-форму (первая колонка list_display —
    // чекбокс _selected_action, поэтому матчим именно по ссылке, а не по первой ячейке).
    for (let i = 0; i < n; i += 1) {
        const link = rows.nth(i).locator('a[href*="/change/"]').first();
        const text = (await link.innerText().catch(() => '')).trim();
        if (text === name) {
            const href = await link.getAttribute('href').catch(() => null);
            const mm = href && href.match(re);
            if (mm) return mm[1];
        }
    }
    throw new Error(`Не найден id модуля "${name}" (курс ${courseId}, модель ${model})`);
}

// Создание одного модуля (+ переводы на все языки). Обязательные поля заполняются на КАЖДОМ языке.
async function createModule(page, info, langPk, cards, m, log) {
    if (m.type === 'video') {
        // videoresource: обязательны course, name, url, weight. url — placeholder (реальную ссылку приложит пользователь).
        await page.goto(`${ADMIN_BASE}/admin/resources/videoresource/add/`, { waitUntil: 'domcontentloaded' });
        await page.fill('#id_course', info.numericId);
        await page.fill('#id_name', m.name);
        await page.fill('#id_description', m.name).catch(() => {});
        await page.fill('#id_url', m.url);
        await page.fill('#id_weight', String(m.weight));
        await page.fill('#id_estimated_time', String(m.estimatedTime)).catch(() => {});
        await page.check('#id_is_active').catch(() => {});
        await saveForm(page, `videoresource:${m.name}`);
        const moduleId = await resolveModuleId(page, info.numericId, m.name, 'videoresource');
        log(`OK  модуль [video] "${m.name}" (id=${moduleId})  ⚠ url=placeholder, замени вручную`);
        // Перевод (videoresourcecontent) на каждый язык: название + продолжительность (url — по желанию).
        for (const c of cards) {
            await page.goto(`${ADMIN_BASE}/admin/resources/videoresourcecontent/add/`, { waitUntil: 'domcontentloaded' });
            await page.fill('#id_course_language', langPk[c.code]);
            await page.fill('#id_module', moduleId);
            await page.fill('#id_name', `${m.name} ${c.code.toUpperCase()}`);
            await page.fill('#id_estimated_time', String(m.estimatedTime)).catch(() => {});
            await saveForm(page, `videoresourcecontent:${m.name}:${c.code}`);
            log(`   OK  контент видео "${m.name}" [${c.code}]`);
        }
        return;
    }
    // article (textresource): editor_type='yfm' обязателен, иначе модуль невалиден и не виден в Лабе.
    await page.goto(`${ADMIN_BASE}/admin/resources/textresource/add/`, { waitUntil: 'domcontentloaded' });
    await page.fill('#id_course', info.numericId);
    await page.fill('#id_name', m.name);
    await page.fill('#id_description', m.name).catch(() => {});
    await page.selectOption('#id_editor_type', 'yfm').catch(() => page.fill('#id_editor_type', 'yfm').catch(() => {}));
    await page.fill('#id_weight', String(m.weight));
    await page.fill('#id_weight_scaled', '0.0');
    await page.fill('#id_estimated_time', String(m.estimatedTime)).catch(() => {});
    await page.fill('#id_content', m.content).catch(() => {});
    await page.check('#id_is_active').catch(() => {});
    await saveForm(page, `textresource:${m.name}`);
    const moduleId = await resolveModuleId(page, info.numericId, m.name, 'textresource');
    log(`OK  модуль [article] "${m.name}" (id=${moduleId})`);
    // Перевод (textresourcecontent) на каждый язык: название + контент + продолжительность.
    for (const c of cards) {
        await page.goto(`${ADMIN_BASE}/admin/resources/textresourcecontent/add/`, { waitUntil: 'domcontentloaded' });
        await page.fill('#id_course_language', langPk[c.code]);
        await page.fill('#id_module', moduleId);
        await page.fill('#id_name', `${m.name} ${c.code.toUpperCase()}`);
        await page.fill('#id_description', m.name).catch(() => {});
        await page.fill('#id_estimated_time', String(m.estimatedTime)).catch(() => {});
        await page.fill('#id_content', `${m.content} (${c.code.toUpperCase()})`).catch(() => {});
        await saveForm(page, `textresourcecontent:${m.name}:${c.code}`);
        log(`   OK  контент статьи "${m.name}" [${c.code}]`);
    }
}

async function getCourseInfo(page, slug) {
    const numericId = await findExactCourseId(page, slug);
    if (!numericId) throw new Error(`Не удалось найти созданный курс '${slug}' в списке`);
    // Родитель learning_outcomes — OneToOne с курсом (его pk = id курса).
    return { numericId, outcomesParentId: numericId };
}

async function apply(plan, chromium) {
    const browser = await chromium.launch();
    const context = await browser.newContext({ storageState: STORAGE_STATE, ignoreHTTPSErrors: true });
    const page = await context.newPage();
    const log = (m) => console.log(m);
    try {
        // 0. авторизация
        await page.goto(`${ADMIN_BASE}/admin/`, { waitUntil: 'domcontentloaded' });
        if (page.url().includes('passport')) {
            throw new Error('storageState протух. Обнови: запусти auth.setup (LMS_ROBOT_HERMIONE_PASSWORD) в проекте.');
        }
        const authorId = await resolveUserId(page, plan.curator);
        log(`author/curator id = ${authorId}`);

        // pre-check: курс с таким slug уже существует?
        await page.goto(`${ADMIN_BASE}/admin/courses/course/?q=${plan.slug}`, { waitUntil: 'domcontentloaded' });
        const existing = await page.locator('#result_list tbody tr').count().catch(() => 0);
        if (existing > 0) {
            if (!plan.force) {
                throw new Error(`Курс со slug '${plan.slug}' уже существует. Удали его, задай другой --slug/--tms-id или используй --force.`);
            }
            const deletedId = await deleteCourseBySlug(page, plan.slug);
            if (deletedId) log(`--force: удалён существующий курс ${plan.slug} (id=${deletedId})`);
            else log(`--force: курса с точным slug '${plan.slug}' не найдено (совпадения были частичными), создаю новый`);
        }

        // 1. Создание курса КАК ЧЕРНОВИК: structure=no_modules, не активен
        //    (правило бэка: активный / multi_modules курс требует модули — их добавим ниже, затем активируем).
        await page.goto(`${ADMIN_BASE}/admin/courses/course/add/`, { waitUntil: 'domcontentloaded' });
        await page.fill('#id_slug', plan.slug);
        await page.fill('#id_name_ru', plan.nameRu);
        await page.selectOption('#id_course_type', plan.courseType).catch(() => {});
        await page.selectOption('#id_structure', 'no_modules').catch(() => {});
        await page.fill('#id_completion_threshold', String(plan.completionThreshold));
        await page.fill('#id_paid_percent', String(plan.paidPercent));
        await page.fill('#id_author', authorId);
        await page.fill('#id_languages', plan.languages.join(','));
        await page.check('#id_migrated_to_multilanguage').catch(() => {});
        // Обязательные для полноценного курса: форма обучения, «обучение от», способ оплаты, категория.
        await page.selectOption('#id_study_mode', plan.studyMode).catch(() => {});
        await page.selectOption('#id_start_mode', plan.startMode).catch(() => {});
        await page.selectOption('#id_payment_method', plan.paymentMethod).catch(() => {});
        await selectCategory(page, plan.category, log);
        // inline: куратор курса (tutor-0-user; поля position в inline нет)
        await page.fill('#id_tutor-0-user', authorId).catch(() => {});
        // inline: "Чему вы научитесь" (родитель) — skills на первом (дефолтном) языке
        const firstCard = plan.cards[0];
        await page.fill('#id_learning_outcomes-0-skills', JSON.stringify({ objects: firstCard.outcomes })).catch(() => {});
        await saveForm(page, 'course (draft)');
        log(`OK  курс-черновик ${plan.slug} создан`);

        // Узнаём числовой id курса и id родителя learning_outcomes
        const info = await getCourseInfo(page, plan.slug);
        log(`   courseId=${info.numericId}  outcomesParentId=${info.outcomesParentId ?? '—'}`);

        // 2. Языки (порядок уже задан полем languages; создаём CourseLanguage-записи)
        //    и сразу собираем map код -> pk (content-модели ссылаются на CourseLanguage по pk).
        const langPk = {};
        for (const code of plan.languages) {
            await page.goto(`${ADMIN_BASE}/admin/courses/courselanguage/add/`, { waitUntil: 'domcontentloaded' });
            await page.fill('#id_course', info.numericId);
            await page.selectOption('#id_language', code);
            await page.check('#id_is_active').catch(() => {});
            await saveForm(page, `courselanguage:${code}`);
            langPk[code] = await resolveLangPk(page, info.numericId, code);
            log(`OK  язык ${code} (pk=${langPk[code]})`);
        }

        // 3. Карточка по языкам: название + "кому подойдёт" (course_language = pk CourseLanguage)
        for (const c of plan.cards) {
            await page.goto(`${ADMIN_BASE}/admin/courses/coursecontent/add/`, { waitUntil: 'domcontentloaded' });
            await page.fill('#id_course', info.numericId);
            await page.fill('#id_course_language', langPk[c.code]);
            await page.fill('#id_name', c.name);
            await page.fill('#id_target_audience_description', c.targetAudience).catch(() => {});
            await saveForm(page, `coursecontent:${c.code}`);
            log(`OK  карточка ${c.code}`);
        }

        // 4. "Чему вы научитесь" по языкам (родитель learning_outcomes, pk = id курса)
        for (const c of plan.cards) {
            await page.goto(`${ADMIN_BASE}/admin/courses/courselearningoutcomescontent/add/`, { waitUntil: 'domcontentloaded' });
            await page.fill('#id_course_learning_outcomes', info.outcomesParentId);
            await page.fill('#id_course_language', langPk[c.code]);
            await page.fill('#id_skills', JSON.stringify({ objects: c.outcomes })).catch(() => {});
            await saveForm(page, `outcomes:${c.code}`);
            log(`OK  чему научитесь ${c.code}`);
        }

        // 5. Модули (article/video), привязка к курсу + переводы на все языки.
        //    КРИТИЧНО (article): editor_type='yfm' — иначе контент невалиден и модуль не виден в Лабе.
        //    Контент модуля ПО КАЖДОМУ ЯЗЫКУ обязателен: без него язык не попадает в
        //    course.supportedLanguages → в конструкторе Лабы нет языковых табов.
        for (const m of plan.modules) {
            await createModule(page, info, langPk, plan.cards, m, log);
        }

        // 6. Финализация: правильная структура + публикация (если нужно)
        await page.goto(`${ADMIN_BASE}/admin/courses/course/${info.numericId}/change/`, { waitUntil: 'domcontentloaded' });
        await page.selectOption('#id_structure', plan.structure).catch(() => {});
        if (plan.publish) {
            for (const f of ['#id_is_active', '#id_show_in_catalog', '#id_show_in_lab']) await page.check(f).catch(() => {});
        }
        await page.locator('input[name="_save"]').click();
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(1000);
        const finErr = await page.locator('.errornote').first().innerText().catch(() => '');
        if (finErr) throw new Error(`финализация (structure/publish): ${finErr.replace(/\s+/g, ' ')}`);

        // Проверяем, что структура реально сохранилась, а не откатилась в no_modules
        // (бэк отклоняет multi_modules, если у курса нет валидных модулей).
        const actualStructure = await page.locator('#id_structure').inputValue().catch(() => '');
        if (actualStructure && actualStructure !== plan.structure) {
            throw new Error(
                `структура не сохранилась: ожидалось "${plan.structure}", в админке "${actualStructure}". ` +
                `Вероятно, модули невалидны (проверь editor_type) — в конструкторе Лабы модулей не будет.`,
            );
        }
        log(`OK  финализация: structure=${actualStructure || plan.structure}, publish=${plan.publish}`);

        log('\nГОТОВО. Проверь курс в admin:');
        log(`  ${ADMIN_BASE}/admin/courses/course/?q=${plan.slug}`);
        log(`  Каталог/Лаборатория (после публикации): https://test.quantum.yandex-team.ru/lab`);
    } finally {
        await browser.close();
    }
}

// --- main ---
const args = parseArgs(process.argv.slice(2));
const plan = buildPlan(args);
printPlan(plan);
if (args.apply) {
    console.log('\n--apply: начинаю запись в testing admin...\n');
    const chromium = await loadChromium();
    await apply(plan, chromium);
}
