# SFT Kit

Software Development Kit for SFT projects.

## Features

- none

## Contributing

This repo is using [NX](https://nx.dev/) as mono-repo management tooling.

- First install nodejs in the current lts version (20).

Then install node dependencies via

```bash
npm install
```

To start hacking on the python parts simply use [uv](https://docs.astral.sh/uv) to install all dependencies.

```bash
uv sync
```

### Packages in this repo

| Name            | Directory             | Package Name              | Technology |
| --------------- | --------------------- | ------------------------- | ---------- |
| sftkit          | `sftkit`              | `sftkit`                  | Python     |
| components      | `web/components`      | `@sftkit/components`      | TypeScript |
| form-components | `web/form-components` | `@sftkit/form-components` | TypeScript |
| modal-provider  | `web/modal-provider`  | `@sftkit/modal-provider`  | TypeScript |
| utils           | `web/utils`           | `@sftkit/utils`           | TypeScript |

#### Linting

To run respective linters on a project run

```bash
npx nx lint <project-name>
```

#### Formatting

```bash
npx nx run sftkit:format
npx nx format
```

#### Testing

```bash
npx nx test <project-name>
```

#### Building

```bash
npx nx build <project-name>
```

## Contact

If you have the desire to perform semi-human interaction,
join our **Matrix** chatroom!

- [`#sfttech:matrix.org`](https://riot.im/app/#/room/#sfttech:matrix.org)

For ideas, problems, ..., use the [issue tracker](https://github.com/SFTtech/sftkit/issues)!

## License

**MIT** license; see [LICENSE](LICENSE).
