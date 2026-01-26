-- AstroCommunity: import any community modules here
-- We import this file in `lazy_setup.lua` before the `plugins/` folder.
-- This guarantees that the specs are processed before any user plugins.

---@type LazySpec
return {
  "AstroNvim/astrocommunity",
  { import = "astrocommunity.pack.lua" },
  { import = "astrocommunity.pack.rust" },
  { import = "astrocommunity.pack.python" },
  { import = "astrocommunity.pack.bash" },
  { import = "astrocommunity.pack.docker" },
  { import = "astrocommunity.pack.go" },
  { import = "astrocommunity.pack.jj" },
  { import = "astrocommunity.pack.markdown" },
  { import = "astrocommunity.completion.copilot-vim-cmp" },
  { import = "astrocommunity.completion.copilot-vim" },
  { import = "astrocommunity.colorscheme.catppuccin" },
  { import = "astrocommunity.game.leetcode-nvim" },
  { import = "astrocommunity.terminal-integration.flatten-nvim" },
  { import = "astrocommunity.terminal-integration.vim-tmux-navigator" },
}
