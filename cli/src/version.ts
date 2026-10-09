/**
 * CLI 版本号的**唯一字面量**。
 *
 * 为什么是一份副本而不是从 `package.json` 读：ESM 导入 JSON 需要额外的 import
 * attributes，而本包刻意保持「运行时不依赖 Node 之外的任何东西」。所以它是一份
 * **被测试钉住的副本**（`test/version.test.ts`），不是第二份真相。
 *
 * ⚠️ 为什么单独成文件：`doctor` 也要用这个数字，而它此前**把这个数字硬编码成
 * `1.0.0`** —— 于是自检报告一直在报错的版本号，而原来的守卫只钉 `index.ts`，
 * **钉不住副本**。现在 index 与 doctor 都从这里取，守卫钉这里、并扫全仓防止再长出
 * 第二处硬编码。
 */
export const CLI_VERSION = '1.1.0';
