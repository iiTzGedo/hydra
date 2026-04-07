# Page snapshot

```yaml
- generic [ref=e2]:
  - generic [ref=e5]:
    - generic [ref=e6]:
      - generic [ref=e7]: H
      - heading "Hydra" [level=1] [ref=e8]
      - paragraph [ref=e9]: Infrastructure Intelligence Platform
    - generic [ref=e10]:
      - heading "Sign in to your account" [level=2] [ref=e11]
      - generic [ref=e12]:
        - generic [ref=e13]:
          - generic [ref=e14]: Username
          - textbox "Username" [ref=e15]:
            - /placeholder: Enter your username
        - generic [ref=e16]:
          - generic [ref=e17]: Password
          - generic [ref=e18]:
            - textbox "Password" [ref=e19]:
              - /placeholder: Enter your password
            - button [ref=e20] [cursor=pointer]:
              - img [ref=e21]
        - generic [ref=e24]:
          - generic [ref=e25]:
            - checkbox "Remember me" [ref=e26]
            - text: Remember me
          - link "Forgot password?" [ref=e27] [cursor=pointer]:
            - /url: /forgot-password
        - button "Sign in" [ref=e28] [cursor=pointer]:
          - img [ref=e29]
          - text: Sign in
      - generic [ref=e32]:
        - text: Don't have an account?
        - link "Sign up" [ref=e33] [cursor=pointer]:
          - /url: /register
    - paragraph [ref=e34]: © 2026 Hydra. AI-powered infrastructure management.
  - region "Notifications alt+T"
```