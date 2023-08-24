podman build -t pr-emailer .
podman run --name pr-emailer -d --rm -it pr-emailer
podman cp pr-emailer:/package/function.zip .
podman stop pr-emailer
