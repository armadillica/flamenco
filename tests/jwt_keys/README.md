To generate a keypair for `ES256`:

    openssl ecparam -genkey -name prime256v1 -noout -out es256-private.pem
    openssl ec -in es256-private.pem -pubout -out es256-public.pem


- `test-private-1.pem` matches `test-public-1.pem`.
- `test-private-2.pem` matches the second key in `test-public-2.pem`.
