# Publishing The Inscription Book with GitHub Pages

The repository includes `.github/workflows/book.yml`, which builds the mdBook documentation site and deploys it from GitHub Actions.

To enable hosting:

1. Open the repository on GitHub.
2. Go to **Settings → Pages**.
3. Set **Build and deployment → Source** to **GitHub Actions**.
4. Push to `master` or run the book workflow manually.

The workflow builds `book/book` with `mdbook build book`, uploads it as a Pages artifact, and deploys it through `actions/deploy-pages`. The public site is expected at:

<https://mattneel.github.io/inscription/>

Pull requests run the book checks and build but do not deploy.
