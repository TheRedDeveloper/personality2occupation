import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';

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
        fs.rmSync(tempBackupDir, { recursive: true, force: true });
        fs.cpSync(gitDir, tempBackupDir, { recursive: true });
      }

      try {
        await baseAdapter.adapt(builder);
      } finally {
        if (hasGit && fs.existsSync(tempBackupDir)) {
          fs.cpSync(tempBackupDir, gitDir, { recursive: true });
          fs.rmSync(tempBackupDir, { recursive: true, force: true });
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
