import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { addToast } from '@heroui/react';
import { useLoginUserApiV1AuthLoginPost } from '@/server/generated';
import { setToken } from '@/view/libs/auth';
import { loginSchema, ILoginForm } from './validation';

export const useLoginPage = () => {
  const router = useRouter();

  const form = useForm<ILoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const loginMutation = useLoginUserApiV1AuthLoginPost({
    mutation: {
      throwOnError: false, // Не пробрасываем ошибки, обрабатываем локально
      onSuccess: (response) => {
        if (response.status === 200 && response.data.access_token) {
          setToken(response.data.access_token);
          addToast({
            title: 'Вход выполнен успешно',
            color: 'success',
          });
          router.push('/chat');
        }
      },
      onError: (error: any) => {
        const status = (error as any)?.status;
        const is401 = status === 401 || error.message?.includes('401');
        
        addToast({
          title: is401 
            ? 'Неверный email или пароль' 
            : error.message || 'Ошибка входа',
          color: 'danger',
        });
      },
    },
  });

  const onSubmit = useCallback(
    (data: ILoginForm) => {
      loginMutation.mutate({
        data: {
          email: data.email,
          password: data.password,
        },
      });
    },
    [loginMutation]
  );

  return {
    form,
    onSubmit,
    isLoading: loginMutation.isPending,
  };
};

