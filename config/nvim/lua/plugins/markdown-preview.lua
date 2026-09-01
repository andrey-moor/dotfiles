-- Open preview in a new Firefox window (stays on current workspace)
return {
  "iamcco/markdown-preview.nvim",
  init = function()
    vim.g.mkdp_browserfunc = "OpenMarkdownPreview"
    vim.cmd([[
      function! OpenMarkdownPreview(url) abort
        silent execute '!firefox --new-window ' .. shellescape(a:url) .. ' &'
      endfunction
    ]])
  end,
}
