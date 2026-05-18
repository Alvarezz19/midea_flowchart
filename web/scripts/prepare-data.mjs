import { mkdir, readdir, readFile, rm, writeFile, copyFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(webRoot, '..');
const sourceDir = path.join(repoRoot, 'build', 'diagrams');
const targetDir = path.join(webRoot, 'public', 'data', 'diagrams');
const manifestPath = path.join(webRoot, 'public', 'data', 'manifest.json');

await rm(targetDir, { recursive: true, force: true });
await mkdir(targetDir, { recursive: true });

const files = (await readdir(sourceDir)).filter((file) => file.endsWith('.json')).sort();
const projects = [];

for (const file of files) {
  const sourcePath = path.join(sourceDir, file);
  const targetPath = path.join(targetDir, file);
  await copyFile(sourcePath, targetPath);
  const diagram = JSON.parse(await readFile(sourcePath, 'utf8'));
  projects.push({
    id: `${diagram.family}/${diagram.project}`,
    family: diagram.family,
    project: diagram.project,
    profile: diagram.profile,
    path: `/data/diagrams/${file}`,
    sourcePath: diagram.source_path,
    overview: diagram.overview.metrics,
    pages: Object.values(diagram.pages).map((page) => ({
      id: page.id,
      label: page.label,
      metrics: page.metrics
    }))
  });
}

await mkdir(path.dirname(manifestPath), { recursive: true });
await writeFile(
  manifestPath,
  JSON.stringify({ generatedAt: new Date().toISOString(), projects }, null, 2),
  'utf8'
);

console.log(`prepared ${projects.length} diagram files`);
