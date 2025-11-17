import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { addToast } from '@heroui/react';
import { useRegisterUserApiV1AuthRegisterPost } from '@/server/generated';
import { registerSchema, IRegisterForm } from './validation';

export const useRegisterPage = () => {
  const router = useRouter();

  const form = useForm<IRegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      password: '',
      confirmPassword: '',
    },
  });

  const registerMutation = useRegisterUserApiV1AuthRegisterPost({
    mutation: {
      onSuccess: () => {
        addToast({
          title: 'Регистрация успешна! Войдите в систему',
          color: 'success',
        });
        router.push('/login');
      },
      onError: (error: any) => {
        addToast({
          title: error.message || 'Ошибка регистрации',
          color: 'danger',
        });
      },
    },
  });

  const onSubmit = useCallback(
    (data: IRegisterForm) => {
      registerMutation.mutate({
        data: {
          username: data.email,
          email: data.email,
          password: data.password,
          role: 1,
        },
      });
    },
    [registerMutation]
  );

  return {
    form,
    onSubmit,
    isLoading: registerMutation.isPending,
  };
};

