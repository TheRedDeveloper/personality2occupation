import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';

function safeRenameSync(src: string, dest: string, retries = 25) {
  for (let i = 0; i < retries; i++) {
    try {
      fs.renameSync(src, dest);
      return;
    } catch (err) {
      if (i === retries - 1) {
        try {
          fs.cpSync(src, dest, { recursive: true });
          fs.rmSync(src, { recursive: true, force: true, maxRetries: 5 });
          return;
        } catch (e) {
          throw err;
        }
      }
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
    }
  }
}

/**
 * Adapter wrapper that preserves `build/.git` across builds.
 */
function gitPreservingAdapter(baseAdapter: any) {
  return {
    name: 'git-preserving-adapter-static',
    async adapt(builder: any) {
      const buildDir = path.resolve('build');
      const gitDir = path.join(buildDir, '.git');
      const tempBackupDir = path.resolve('.git-build-backup');

      const hasGit = fs.existsSync(gitDir);
      if (hasGit) {
        if (fs.existsSync(tempBackupDir)) {
          fs.rmSync(tempBackupDir, { recursive: true, force: true, maxRetries: 3 });
        }
        safeRenameSync(gitDir, tempBackupDir);
      }

      try {
        await baseAdapter.adapt(builder);
      } finally {
        if (hasGit && fs.existsSync(tempBackupDir)) {
          if (fs.existsSync(gitDir)) {
            fs.rmSync(gitDir, { recursive: true, force: true, maxRetries: 3 });
          }
          safeRenameSync(tempBackupDir, gitDir);
        }
      }
    }
  };
}

export default defineConfig({
  plugins: [
    sveltekit({
      adapter: gitPreservingAdapter(
        adapter({
          pages: 'build',
          assets: 'build',
          fallback: '404.html',
          precompress: false,
          strict: true
        })
      ),
      paths: {
        relative: true
      }
    })
  ]
});
