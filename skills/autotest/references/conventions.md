# Конвенции Playwright e2e в LMS (справочник для генерации spec)

Пути от корня проекта `/Users/yusokolova/arcadia4/hrtech/frontend/services/lms`.
Конфиг — `playwright.config.ts`, `testDir: tests/playwright/tests`.

## Куда класть

`tests/playwright/tests/participantsInterface/<раздел>/<Название>.spec.ts` — spec группируются по разделу UI
(`catalog`, `courseCard`, `trainings`, `interviewLoop`, `spaLayout`, …). Page-objects — локально в
`<раздел>/page-objects/` (общие тренинги/сотрудники — в корневом `tests/playwright/page-objects/`).

## Импорт

- Обычный тест: `import { expect, test } from '@playwright/test';`
- Нужны фикстуры (`adminApiClient`, `trainingsCheckMock`): `import { expect, test } from '../../fixtures';`
  (глубина `../` зависит от вложенности). Фикстура `onboardingDisabled` — авто (`{ auto: true }`),
  подключать не нужно.
- Аннотации: `import { annotations } from '<...>/tests/playwright/utils/annotations.ts';`

## Скелет spec

```ts
import { expect, test } from '@playwright/test';

import { annotations } from '../../../utils/annotations';
import { CoursePage } from './page-objects/course-page';

test(
    '[Карточки курса][Мультиязычный курс]: <краткое название сценария>',
    annotations('https://tms.yandex-team.ru/projects/lm/testcases/<id>'),
    async ({ page }) => {
        const SLUG = 'slug_tmslv<id>';         // созданный через create-course (или готовый курс)
        const coursePage = new CoursePage(page, SLUG);

        await test.step('<Action шага 1 — дословно из кейса>', async () => {
            await coursePage.goto();
            await expect(coursePage.header.name, '<Expected — человекочитаемо>').toHaveText('…');
        });

        await test.step('<Action шага 2 — дословно>', async () => {
            await coursePage.languageTabs.getTabByName('English').click();
            await expect(coursePage.header.ctaButton, '<Expected>').toHaveText('…');
        });
    },
);
```

Правила:
- **`annotations(url[, tags])`** — обязательно вторым аргументом `test()`. Даёт TMS-линк и tms-sync
  (`.../testcases/491` → `lm-491`). Теги — массивом: `annotations(url, ['@regress'])`. `@nonparallel`
  исключается из CI-параллели. Тега `regression_new` в коде нет.
- **`test.step('<Action>')`** — заголовок = ТОЛЬКО действие, **дословно** как Action в кейсе
  (по нему синкаются STEPS_AND_EXPECTATIONS в TMS). Результат проверки — НЕ в заголовке.
- **`expect(locator, '<описание>')`** — второй аргумент строка-описание Expected на русском.
- Номер кейса в заголовок теста НЕ выносить (он в annotations). Заголовок — `[Раздел][Подраздел]: суть`.
- `test.describe('…')` — опционально для группировки нескольких тестов.

## Page-objects

Класс с `readonly` локаторами в конструкторе. Приоритет локаторов: `getByTestId` → `getByRole` →
`.locator('#id'/'.Class')` (последнее — с комментарием). Под-объекты принимают `root: Locator`.

```ts
export class CoursePage {
    public constructor(page: Page, slug: string) {
        this.slug = slug;
        this.header = new Header(page.getByTestId('Header'));
        this.languageTabs = new LanguageSelector(page.getByTestId('language-selector').getByRole('tablist'));
        this.targetAudience = page.locator('#TargetAudience');   // «кому подойдёт»
        this.outcomes = page.locator('#Outcomes');               // «чему научитесь»
    }
    public async goto(language?: string) {
        await this.page.goto('/courses/' + this.slug + (language ? `?language=${language}` : ''));
    }
}
// LanguageSelector: getTabByName(name) => root.getByRole('tab', { name })
```

Новый `data-testid` искать в `src/client/screens/<Раздел>/` (`grep -rn 'data-testid=' src/client/screens/Course`).
Пример: `Header`, `Header-CourseName` (`src/client/screens/Course/components/Header/Header.tsx`),
`language-selector` (`.../LanguageSelector/LanguageSelector.tsx`).

## Данные и teardown

- Тестовый МЯ-курс создаётся скиллом `create-course` (slug `slug_tmslv<id>`). Готовые курсы: `standard-course`,
  `standard-course-with-form`, `standard-course-with-confirmation`.
- Мультиязычность проверяется контентом курса: `goto('<code>')` (`?language=`) или клик таба
  `coursePage.languageTabs.getTabByName('English').click()`. Отдельного «языкового робота» нет.
- Если тест создаёт данные пользователя (запись на курс/тренинг) — идемпотентная чистка через
  `adminApiClient` в начале и в `finally` (см. `utils/reset-training-enrollment.ts`,
  `trainings/Trainings.spec.ts`). Смена роли — werewolf-трансформация с чисткой в teardown.

## Авторизация

Глобально через `storageState` (`authUser.json`, робот `robot-lms-hermione`) — задаётся в конфиге, в тесте
ничего делать не нужно. `teardownUser.json` (робот `robot-lms-e2e-admin`) использует только `AdminApiClient`.

## Запуск

```bash
source ./tools/scripts/prepare-env-e2e.sh && pnpm run playwright test <spec> -g "<заголовок>"
```
Проекты `setup`→`warm-up`→`chromium` прогонятся автоматически (генерируют storageState). В `goto` —
относительные пути (`/courses/...`), `baseURL` подставляется сам.

## Файлы-образцы

- `participantsInterface/catalog/Catalog.spec.ts` — простой, `annotations`, без фикстур.
- `participantsInterface/courseCard/MultilanguageCourse.spec.ts` — МЯ-курс, `goto(lang)`, языковые табы.
- `participantsInterface/trainings/Trainings.spec.ts` — `adminApiClient` + setup/teardown в try/finally.
- `participantsInterface/courseCard/page-objects/{course-page,language-selector,header}.ts` — паттерн POM.
- `utils/annotations.ts` — TMS-линк.
