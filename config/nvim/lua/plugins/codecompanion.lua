return {
  {
    "olimorris/codecompanion.nvim",
    name = "codecompanion",
    opts = {
      adapters = {
        anthropic = function()
          return require("codecompanion.adapters").extend("anthropic", {
            env = {
              api_key = "cmd:op read op://Employee/Anthropic/API --no-newline",
            },
            schema = {
              model = {
                default = "anthropic/claude-3.7-sonnet",
              },
            },
          })
        end,
      },
      strategies = {
        chat = {
          keymaps = {
            send = {
              modes = { n = "<C-s>", i = "<C-s>" },
            },
            close = {
              modes = { n = "<C-c>", i = "<C-c>" },
            },
            completion = {
              modes = { i = "<C-/>" },
              callback = "keymaps.completion",
              description = "Completion Menu",
            },
          },
        },
      },
      display = {
        chat = {
          show_header_separator = true,
          -- show_settings = true,
          show_references = true,
          show_token_count = true,
          window = {
            opts = {
              number = false,
              signcolumn = "no",
            },
          },
        },
      },
    },
    dependencies = {
      { "nvim-lua/plenary.nvim" },
      { "nvim-treesitter/nvim-treesitter" },
      {
        "AstroNvim/astrocore",
        ---@param opts AstroCoreOpts
        opts = function(_, opts)
          local maps = assert(opts.mappings)
          local prefix = opts.options.g.copilot_chat_prefix or "<Leader>I"

          -- Set up the main prefix with description
          maps.n["<C-a>"] =
            { "<cmd>CodeCompanionActions<cr>", desc = "Code Companion Actions", noremap = true, silent = true }
          maps.v["<C-a>"] =
            { "<cmd>CodeCompanionActions<cr>", desc = "Code Companion Actions", noremap = true, silent = true }

          -- Set up the chat toggle mapping
          maps.n[prefix] =
            { "<cmd>CodeCompanionChat Toggle<cr>", desc = "Code Companion Chat Toggle", noremap = true, silent = true }
          maps.v[prefix] =
            { "<cmd>CodeCompanionChat Toggle<cr>", desc = "Code Companion Chat Toggle", noremap = true, silent = true }

          -- Visual mode "ga" mapping
          maps.v["ga"] =
            { "<cmd>CodeCompanionChat Add<cr>", desc = "Code Companion Chat Add", noremap = true, silent = true }

          -- Command abbreviation (this would typically be outside the opts function in AstroNvim)
          vim.cmd [[cab cc CodeCompanion]]
        end,
      },
    },
  },
}
